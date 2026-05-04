<template>
  <div class="results-view">
    <div class="results-header">
      <h1 class="results-title">{{ t('results.title') }}</h1>
      <p class="results-subtitle">{{ t('results.subtitle') }}</p>
    </div>

    <div v-if="loading" class="results-loading">
      <div class="spinner" />
      <span>Loading...</span>
    </div>

    <div v-else-if="groupedResults.length === 0" class="results-empty">
      <p>{{ t('results.noResults') }}</p>
    </div>

    <div v-else class="results-list">
      <div
        v-for="group in groupedResults"
        :key="group.sessionId"
        class="result-group"
      >
        <button
          class="group-header"
          @click="toggleGroup(group.sessionId)"
        >
          <span class="group-chevron" :class="{ open: isOpen(group.sessionId) }">
            ▶
          </span>
          <span class="group-name">{{ group.sessionName }}</span>
          <span class="group-count">{{ group.dirs.length }} dirs</span>
        </button>

        <div v-show="isOpen(group.sessionId)" class="group-body">
          <div
            v-for="dir in group.dirs"
            :key="dir.path"
            class="result-dir"
          >
            <div class="dir-header">
              <span class="dir-icon">📁</span>
              <span class="dir-name">{{ dir.base }}</span>
              <span class="dir-path">{{ dir.path }}</span>
            </div>
            <ul class="dir-files">
              <li
                v-for="f in dir.files"
                :key="f.name"
                class="dir-file"
              >
                <span class="file-icon">{{ fileIcon(f.name.slice(f.name.lastIndexOf('.'))) }}</span>
                <span class="file-name">{{ f.name }}</span>
                <span class="file-size">{{ formatSize(f.size) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { getResults } from '@/api/ai'
import { fileIcon } from '@/utils/fileIcon'
import type { ResultDir } from '@/types/file'

const { t } = useI18n()
const sessionStore = useSessionStore()

const loading = ref(false)
const results = ref<ResultDir[]>([])
const openGroups = ref<Set<string>>(new Set())

interface GroupedResult {
  sessionId: string
  sessionName: string
  dirs: ResultDir[]
}

const groupedResults = computed<GroupedResult[]>(() => {
  const map = new Map<string, ResultDir[]>()
  for (const dir of results.value) {
    // Extract session id from path like "sessions/{id}/..."
    const parts = dir.path.split('/')
    const sessionId = parts.length > 1 ? parts[1] : 'unknown'
    if (!map.has(sessionId)) {
      map.set(sessionId, [])
    }
    map.get(sessionId)!.push(dir)
  }

  const groups: GroupedResult[] = []
  for (const [sessionId, dirs] of map) {
    const session = sessionStore.sessions.find((s) => s.id === sessionId)
    groups.push({
      sessionId,
      sessionName: session?.name || sessionId,
      dirs,
    })
  }
  return groups
})

function isOpen(sessionId: string): boolean {
  return openGroups.value.has(sessionId)
}

function toggleGroup(sessionId: string): void {
  if (openGroups.value.has(sessionId)) {
    openGroups.value.delete(sessionId)
  } else {
    openGroups.value.add(sessionId)
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadResults(): Promise<void> {
  loading.value = true
  try {
    // Gather results from all sessions
    await sessionStore.loadSessions()
    const allResults: ResultDir[] = []
    for (const session of sessionStore.sessions) {
      try {
        const res = await getResults(session.id)
        if (Array.isArray(res.results)) {
          for (const item of res.results) {
            if (isResultDir(item)) {
              allResults.push(item)
            }
          }
        }
      } catch {
        // ignore per-session errors
      }
    }
    results.value = allResults
  } finally {
    loading.value = false
  }
}

function isResultDir(item: unknown): item is ResultDir {
  const d = item as Record<string, unknown>
  return typeof d?.path === 'string' && Array.isArray(d?.files)
}

onMounted(() => {
  loadResults()
})
</script>

<style scoped>
.results-view {
  padding: 1.5rem;
  height: 100%;
  overflow: auto;
}

.results-header {
  margin-bottom: 1.5rem;
}

.results-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.25rem;
}

.results-subtitle {
  font-size: 0.875rem;
  color: var(--sub);
}

.results-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--sub);
  font-size: 0.875rem;
}

.spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.results-empty {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--sub);
  font-size: 0.875rem;
}

.result-group {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.625rem;
  margin-bottom: 0.75rem;
  overflow: hidden;
}

.group-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text);
  text-align: left;
}

.group-header:hover {
  background: var(--bg);
}

.group-chevron {
  font-size: 0.625rem;
  transition: transform 0.2s;
  color: var(--sub);
}

.group-chevron.open {
  transform: rotate(90deg);
}

.group-name {
  flex: 1;
  font-weight: 500;
}

.group-count {
  font-size: 0.75rem;
  color: var(--sub);
  background: var(--bg);
  padding: 0.125rem 0.5rem;
  border-radius: 0.75rem;
}

.group-body {
  padding: 0 1rem 1rem;
}

.result-dir {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--bg);
  border-radius: 0.5rem;
}

.dir-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.dir-name {
  font-weight: 500;
  font-size: 0.875rem;
  color: var(--text);
}

.dir-path {
  font-size: 0.75rem;
  color: var(--sub);
  font-family: monospace;
}

.dir-files {
  list-style: none;
  padding-left: 1.5rem;
}

.dir-file {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0;
  font-size: 0.8125rem;
  color: var(--text);
}

.file-size {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--sub);
}
</style>

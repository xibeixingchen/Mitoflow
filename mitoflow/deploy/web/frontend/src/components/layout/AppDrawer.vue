<template>
  <aside
    class="app-drawer"
    :class="{ open }"
    role="complementary"
    aria-label="Session drawer"
    :aria-expanded="open"
  >
    <div class="drawer-header">
      <span class="drawer-title">{{ t('chat.session') }}</span>
      <button
        class="close-btn"
        aria-label="Close session drawer"
        @click="onClose"
      >
        ✕
      </button>
    </div>

    <div class="drawer-search">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        :aria-label="t('chat.searchSessions')"
        :placeholder="t('chat.searchSessions')"
      />
    </div>

    <button
      class="new-session-btn"
      :aria-label="t('chat.newChat')"
      @click="onNewSession"
    >
      <span>+</span>
      <span>{{ t('chat.newChat') }}</span>
    </button>

    <div class="session-list" role="list" aria-label="Chat sessions">
      <!-- Skeleton loading -->
      <template v-if="sessionStore.loading">
        <div v-for="n in 6" :key="n" class="session-item skeleton-row">
          <div class="skeleton skeleton-circle" style="width:28px;height:28px;flex-shrink:0;" />
          <div style="flex:1;display:flex;flex-direction:column;gap:0.375rem;">
            <div class="skeleton skeleton-text" style="width:65%;" />
            <div class="skeleton skeleton-text short" />
          </div>
        </div>
      </template>

      <div
        v-for="session in filteredSessions"
        :key="session.id"
        class="session-item"
        :class="{ active: sessionStore.activeSessionId === session.id }"
        role="listitem"
        tabindex="0"
        @click="onSelect(session.id)"
        @keydown.enter="onSelect(session.id)"
      >
        <div class="session-info">
          <span class="session-name">
            <span v-if="session.pinned" class="pin-icon">📌</span>
            {{ session.name }}
          </span>
          <span class="session-preview">{{ session.first_message || t('chat.noPreview') }}</span>
        </div>
        <div class="session-actions">
          <button class="action-btn" :title="t('chat.rename')" @click.stop="onRenameInline(session.id)">✏️</button>
          <button class="action-btn" :title="session.pinned ? t('chat.unpin') : t('chat.pin')" @click.stop="onTogglePinInline(session.id, !session.pinned)">
            {{ session.pinned ? '📍' : '📌' }}
          </button>
          <button class="action-btn" :title="t('chat.export')" @click.stop="showExportMenu(session.id, $event)">⬇️</button>
          <button class="action-btn danger" :title="t('chat.delete')" @click.stop="onDeleteInline(session.id)">🗑️</button>
        </div>
      </div>

      <div v-if="filteredSessions.length === 0" class="no-sessions">
        {{ t('chat.noSessions') }}
      </div>
    </div>

    <!-- Export Menu -->
    <div
      v-if="exportMenu.visible"
      class="export-menu"
      :style="{ top: `${exportMenu.y}px`, left: `${exportMenu.x}px` }"
      @click.stop
    >
      <button class="export-item" @click="doExport('md')">{{ t('chat.exportMd') }}</button>
      <button class="export-item" @click="doExport('txt')">{{ t('chat.exportTxt') }}</button>
    </div>

    <div class="drawer-footer">
      <span class="status-dot" :class="{ online: isOnline }" />
      <span class="status-text">{{ isOnline ? t('status.connected') : t('status.offline') }}</span>
    </div>

  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { fetchMessages } from '@/api/ai'
import { apiClient } from '@/api/client'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'select', id: string): void
  (e: 'newSession'): void
}>()

const { t } = useI18n()
const sessionStore = useSessionStore()

const searchQuery = ref('')
const isOnline = ref(false)
const exportMenu = ref({ visible: false, x: 0, y: 0, sessionId: '' })

// Check backend health periodically
async function checkHealth() {
  try {
    const res = await apiClient.get('/health')
    isOnline.value = res.data?.status === 'healthy'
  } catch {
    isOnline.value = false
  }
}
checkHealth()
setInterval(checkHealth, 30000)  // every 30s

const filteredSessions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sessionStore.sortedSessions
  return sessionStore.searchSessions(q)
})

function onClose(): void {
  emit('update:open', false)
}

function onSelect(id: string): void {
  emit('select', id)
}

function onNewSession(): void {
  emit('newSession')
}

/* Inline actions */

async function onRenameInline(id: string): Promise<void> {
  const current = sessionStore.sessions.find((s) => s.id === id)
  if (!current) return
  const name = window.prompt(t('chat.renamePrompt') || 'Rename session:', current.name)
  if (name && name !== current.name) {
    await sessionStore.renameSession(id, name)
  }
}

async function onTogglePinInline(id: string, pinned: boolean): Promise<void> {
  await sessionStore.pinSession(id, pinned)
}

async function onDeleteInline(id: string): Promise<void> {
  if (window.confirm(t('chat.deleteConfirm') || 'Delete this session?')) {
    await sessionStore.deleteSession(id)
  }
}

/* Export menu */

function showExportMenu(sessionId: string, event: MouseEvent): void {
  exportMenu.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    sessionId,
  }
}

function hideExportMenu(): void {
  exportMenu.value.visible = false
}

async function doExport(format: 'md' | 'txt'): Promise<void> {
  const id = exportMenu.value.sessionId
  hideExportMenu()
  try {
    const resp = await fetchMessages(id)
    const messages = resp.messages || []
    let content = ''
    if (format === 'md') {
      content = messages.map((m) => `**${m.role}:**\n\n${m.content}\n\n---\n`).join('\n')
    } else {
      content = messages.map((m) => `[${m.role}]\n${m.content}\n`).join('\n---\n\n')
    }
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const session = sessionStore.sessions.find((s) => s.id === id)
    const filename = `${session?.name || 'session'}_${id.slice(0, 8)}.${format}`
    a.download = filename.replace(/[^a-zA-Z0-9\-_\.]/g, '_')
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    alert(t('chat.exportFailed') || 'Export failed')
  }
}

onMounted(() => {
  sessionStore.loadSessions()
  document.addEventListener('click', hideExportMenu)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', hideExportMenu)
})
</script>

<style scoped>
.app-drawer {
  position: fixed;
  left: var(--nav-w);
  top: 0;
  bottom: 0;
  width: var(--drawer-w);
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transform: translateX(-100%);
  transition: transform 0.25s ease;
  z-index: 40;
}

.app-drawer.open {
  transform: translateX(0);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
}

.drawer-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
}

.close-btn {
  width: 28px;
  height: 28px;
  border-radius: 0.375rem;
  border: none;
  background: transparent;
  color: var(--sub);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
}

.close-btn:hover {
  background: var(--bg);
  color: var(--text);
}

.drawer-search {
  padding: 0.75rem 1rem;
}

.search-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.8125rem;
}

.search-input::placeholder {
  color: var(--sub);
}

.new-session-btn {
  margin: 0 1rem 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  padding: 0.5rem;
  border-radius: 0.625rem;
  border: 1px dashed var(--border);
  background: transparent;
  color: var(--accent);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.15s;
}

.new-session-btn:hover {
  border-color: var(--accent);
  background: var(--bg);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 0.5rem;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}

.session-item:hover {
  background: var(--bg);
}

.session-item.active {
  background: var(--bg);
}

.session-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.5rem;
  bottom: 0.5rem;
  width: 3px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}

.session-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.pin-icon {
  font-size: 0.625rem;
  margin-right: 0.25rem;
}

.session-name {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-preview {
  font-size: 0.75rem;
  color: var(--sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-actions {
  display: flex;
  gap: 0.125rem;
  opacity: 0;
  transition: opacity 0.15s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.action-btn {
  width: 24px;
  height: 24px;
  border-radius: 0.375rem;
  border: none;
  background: transparent;
  font-size: 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sub);
  transition: background 0.15s;
}

.action-btn:hover {
  background: var(--surface);
  color: var(--text);
}

.action-btn.danger:hover {
  background: color-mix(in srgb, var(--red) 12%, transparent);
  color: var(--red);
}

.no-sessions {
  text-align: center;
  padding: 2rem 1rem;
  font-size: 0.8125rem;
  color: var(--sub);
}

.drawer-footer {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.75rem;
  color: var(--sub);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--red);
}

.status-dot.online {
  background: var(--green);
}

/* Skeleton rows */
.skeleton-row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.625rem 0.75rem;
  pointer-events: none;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .app-drawer {
    left: 0;
    width: 100vw;
    z-index: 100;
  }
  .drawer-header {
    padding-top: env(safe-area-inset-top, 0.5rem);
  }
}

/* Export Menu */
.export-menu {
  position: fixed;
  z-index: 200;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  box-shadow: 0 4px 16px color-mix(in srgb, var(--text) 10%, transparent);
  padding: 0.25rem;
  min-width: 120px;
}

.export-item {
  width: 100%;
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 0.8125rem;
  cursor: pointer;
}

.export-item:hover {
  background: var(--bg);
}
</style>

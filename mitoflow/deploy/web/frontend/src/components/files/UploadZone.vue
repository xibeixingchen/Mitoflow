<template>
  <div class="upload-zone-page">
    <h1 class="upload-title">{{ t('files.title') }}</h1>

    <div
      class="drop-zone"
      :class="{ dragging }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="onClickZone"
    >
      <div class="drop-icon">📤</div>
      <p class="drop-text">{{ t('files.dropzone') }}</p>
      <p class="drop-hint">Click or drag files here</p>
      <input
        ref="fileInput"
        type="file"
        multiple
        class="file-input"
        @change="onFileSelect"
      />
    </div>

    <div v-if="fileStore.files.length > 0" class="file-list">
      <div
        v-for="f in fileStore.files"
        :key="f.name"
        class="file-item"
      >
        <span class="file-icon">{{ fileIcon(f.name.slice(f.name.lastIndexOf('.'))) }}</span>
        <div class="file-info">
          <span class="file-name">{{ f.name }}</span>
          <span class="file-meta">{{ formatSize(f.size) }}</span>
        </div>
        <button class="file-delete" @click="onDelete(f.name)">✕</button>
      </div>
    </div>

    <div v-else class="no-files">{{ t('files.noFiles') }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFileStore } from '@/stores/file'
import { useSessionStore } from '@/stores/session'
import { fileIcon } from '@/utils/fileIcon'

const { t } = useI18n()
const fileStore = useFileStore()
const sessionStore = useSessionStore()

const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

function onClickZone(): void {
  fileInput.value?.click()
}

function onDrop(e: DragEvent): void {
  dragging.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    handleFiles(Array.from(files))
  }
}

function onFileSelect(e: Event): void {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    handleFiles(Array.from(target.files))
    target.value = ''
  }
}

async function handleFiles(files: File[]): Promise<void> {
  const sessionId = sessionStore.activeSessionId
  if (!sessionId) {
    const s = await sessionStore.createSession()
    await fileStore.uploadFiles(s.id, files)
    return
  }
  await fileStore.uploadFiles(sessionId, files)
}

async function onDelete(name: string): Promise<void> {
  const sessionId = sessionStore.activeSessionId
  if (!sessionId) return
  await fileStore.deleteFile(name, sessionId)
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped>
.upload-zone-page {
  max-width: 800px;
  margin: 0 auto;
}

.upload-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 1.25rem;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 3rem 2rem;
  border: 2px dashed var(--border);
  border-radius: 0.75rem;
  background: var(--surface);
  cursor: pointer;
  transition: all 0.15s;
}

.drop-zone.dragging {
  border-color: var(--accent);
  background: var(--bg);
}

.drop-zone:hover {
  border-color: var(--accent);
}

.drop-icon {
  font-size: 2.5rem;
}

.drop-text {
  font-size: 0.9375rem;
  color: var(--text);
  font-weight: 500;
}

.drop-hint {
  font-size: 0.8125rem;
  color: var(--sub);
}

.file-input {
  display: none;
}

.file-list {
  margin-top: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.625rem;
}

.file-icon {
  font-size: 1.25rem;
}

.file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.file-name {
  font-size: 0.875rem;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: 0.75rem;
  color: var(--sub);
}

.file-delete {
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
}

.file-delete:hover {
  background: color-mix(in srgb, var(--red) 10%, transparent);
  color: var(--red);
}

.no-files {
  margin-top: 1.25rem;
  text-align: center;
  padding: 2rem;
  color: var(--sub);
  font-size: 0.875rem;
}
</style>

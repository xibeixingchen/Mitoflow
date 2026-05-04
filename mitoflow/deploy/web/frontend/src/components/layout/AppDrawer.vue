<template>
  <aside class="app-drawer" :class="{ open }">
    <div class="drawer-header">
      <span class="drawer-title">{{ t('chat.session') }}</span>
      <button class="close-btn" @click="onClose">
        ✕
      </button>
    </div>

    <div class="drawer-search">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        :placeholder="t('chat.searchSessions')"
      />
    </div>

    <button class="new-session-btn" @click="onNewSession">
      <span>+</span>
      <span>{{ t('chat.newChat') }}</span>
    </button>

    <div class="session-list">
      <div
        v-for="session in filteredSessions"
        :key="session.id"
        class="session-item"
        :class="{ active: sessionStore.activeSessionId === session.id }"
        @click="onSelect(session.id)"
        @contextmenu.prevent="showContextMenu($event, session.id)"
      >
        <span class="session-pin" v-if="session.pinned">📌</span>
        <span class="session-name">{{ session.name }}</span>
        <span class="session-preview">{{ session.first_message }}</span>
      </div>

      <div v-if="filteredSessions.length === 0" class="no-sessions">
        {{ t('chat.noSessions') }}
      </div>
    </div>

    <div class="drawer-footer">
      <span class="status-dot" :class="{ online: isOnline }" />
      <span class="status-text">{{ isOnline ? t('status.connected') : t('status.offline') }}</span>
    </div>

    <!-- Context Menu -->
    <div
      v-if="contextMenu.visible"
      class="context-menu"
      :style="{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }"
      @click.stop
    >
      <button class="ctx-item" @click="onRename">
        {{ t('chat.rename') }}
      </button>
      <button class="ctx-item" @click="onTogglePin">
        {{ pinnedTarget ? t('chat.unpin') : t('chat.pin') }}
      </button>
      <button class="ctx-item ctx-danger" @click="onDelete">
        {{ t('chat.delete') }}
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'

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
const isOnline = ref(true)
const contextMenu = ref({ visible: false, x: 0, y: 0, sessionId: '' })

const filteredSessions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sessionStore.sortedSessions
  return sessionStore.searchSessions(q)
})

const pinnedTarget = computed(() => {
  const s = sessionStore.sessions.find((s) => s.id === contextMenu.value.sessionId)
  return s?.pinned || false
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

function showContextMenu(event: MouseEvent, sessionId: string): void {
  contextMenu.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    sessionId,
  }
}

function hideContextMenu(): void {
  contextMenu.value.visible = false
}

async function onRename(): Promise<void> {
  const id = contextMenu.value.sessionId
  const current = sessionStore.sessions.find((s) => s.id === id)
  if (!current) return
  const name = window.prompt('Rename session:', current.name)
  if (name && name !== current.name) {
    await sessionStore.renameSession(id, name)
  }
  hideContextMenu()
}

async function onTogglePin(): Promise<void> {
  const id = contextMenu.value.sessionId
  const s = sessionStore.sessions.find((s) => s.id === id)
  if (s) {
    await sessionStore.pinSession(id, !s.pinned)
  }
  hideContextMenu()
}

async function onDelete(): Promise<void> {
  const id = contextMenu.value.sessionId
  if (window.confirm(t('chat.deleteConfirm'))) {
    await sessionStore.deleteSession(id)
  }
  hideContextMenu()
}

onMounted(() => {
  sessionStore.loadSessions()
  document.addEventListener('click', hideContextMenu)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', hideContextMenu)
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
  flex-direction: column;
  gap: 0.125rem;
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

.session-pin {
  font-size: 0.625rem;
  position: absolute;
  right: 0.5rem;
  top: 0.5rem;
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

/* Context Menu */
.context-menu {
  position: fixed;
  z-index: 200;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  box-shadow: 0 4px 16px color-mix(in srgb, var(--text) 10%, transparent);
  padding: 0.25rem;
  min-width: 140px;
}

.ctx-item {
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

.ctx-item:hover {
  background: var(--bg);
}

.ctx-danger {
  color: var(--red);
}
</style>

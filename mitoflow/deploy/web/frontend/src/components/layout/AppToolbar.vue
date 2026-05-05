<template>
  <header class="app-toolbar">
    <router-link to="/" class="toolbar-logo" title="MitoFlow">
      <img src="/logo.png" alt="MitoFlow" class="logo-img" />
    </router-link>
    <button
      class="toolbar-btn hamburger"
      aria-label="Toggle session drawer"
      @click="onToggleDrawer"
    >
      ☰
    </button>
    <h2 class="toolbar-title">{{ title }}</h2>
    <button
      v-if="showResultsToggle"
      class="toolbar-btn"
      aria-label="Toggle results panel"
      @click="onToggleResults"
    >
      📊
    </button>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps<{
  title: string
}>()

const emit = defineEmits<{
  (e: 'toggleDrawer'): void
  (e: 'toggleResults'): void
}>()

const route = useRoute()

const showResultsToggle = computed(() => {
  const path = route.path
  return path.startsWith('/chat') || path.startsWith('/tools')
})

function onToggleDrawer(): void {
  emit('toggleDrawer')
}

function onToggleResults(): void {
  emit('toggleResults')
}
</script>

<style scoped>
.app-toolbar {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.toolbar-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  border: none;
  background: transparent;
  color: var(--sub);
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.15s;
}

.toolbar-btn:hover {
  background: var(--bg);
  color: var(--text);
}

.toolbar-logo {
  display: flex;
  align-items: center;
  text-decoration: none;
  margin-right: 0.25rem;
}

.logo-img {
  width: 28px;
  height: 28px;
  border-radius: 0.375rem;
  object-fit: contain;
}

.toolbar-title {
  flex: 1;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>

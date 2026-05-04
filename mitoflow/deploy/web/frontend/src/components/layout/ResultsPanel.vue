<template>
  <aside class="results-panel" :class="{ open }">
    <div class="panel-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: currentTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </button>
    </div>

    <div class="panel-body">
      <div v-if="currentTab === 'files'" class="tab-content">
        <FileTree />
      </div>
      <div v-else-if="currentTab === 'preview'" class="tab-content">
        <div class="empty-state">
          <span class="empty-icon">👁</span>
          <p>Select a file to preview</p>
        </div>
      </div>
      <div v-else-if="currentTab === 'pipeline'" class="tab-content">
        <div class="empty-state">
          <span class="empty-icon">🔗</span>
          <p>{{ t('results.pipelineEmpty') }}</p>
        </div>
      </div>
    </div>

    <button class="panel-close" @click="onClose">
      ✕
    </button>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import FileTree from '@/components/results/FileTree.vue'

const props = defineProps<{
  open: boolean
  activeTab: string
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'switchTab', tab: string): void
}>()

const { t } = useI18n()

const tabs = [
  { key: 'files', icon: '📁', label: t('results.filesTab') },
  { key: 'preview', icon: '👁', label: t('results.previewTab') },
  { key: 'pipeline', icon: '🔗', label: t('results.pipelineTab') },
]

const currentTab = ref(props.activeTab)

watch(() => props.activeTab, (val) => {
  currentTab.value = val
})

function switchTab(tab: string): void {
  currentTab.value = tab
  emit('switchTab', tab)
}

function onClose(): void {
  emit('update:open', false)
}
</script>

<style scoped>
.results-panel {
  position: fixed;
  right: 0;
  top: 44px;
  bottom: 0;
  width: var(--results-w);
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.25s ease;
  z-index: 30;
}

.results-panel.open {
  transform: translateX(0);
}

.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  padding: 0.5rem;
  border: none;
  background: transparent;
  color: var(--sub);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
  border-bottom: 2px solid transparent;
}

.tab-btn:hover {
  color: var(--text);
  background: var(--bg);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-icon {
  font-size: 0.875rem;
}

.tab-label {
  white-space: nowrap;
}

.panel-body {
  flex: 1;
  overflow: auto;
}

.tab-content {
  height: 100%;
  overflow: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 0.5rem;
  color: var(--sub);
  font-size: 0.8125rem;
  padding: 2rem;
  text-align: center;
}

.empty-icon {
  font-size: 2rem;
  opacity: 0.5;
}

.panel-close {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 24px;
  height: 24px;
  border-radius: 0.375rem;
  border: none;
  background: transparent;
  color: var(--sub);
  font-size: 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel-close:hover {
  background: var(--bg);
  color: var(--text);
}
</style>

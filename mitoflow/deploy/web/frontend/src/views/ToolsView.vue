<template>
  <div class="tools-view">
    <div class="tools-tabs">
      <button class="tab" :class="{ active: organelle === 'mito' }" @click="organelle = 'mito'">
        🧬 线粒体
      </button>
      <button class="tab" :class="{ active: organelle === 'chloro' }" @click="organelle = 'chloro'">
        🌿 叶绿体
      </button>
    </div>
    <ModuleGrid mode="modules" :category="organelle === 'chloro' ? 'cgas' : 'mito'" @ai-prompt="onAiPrompt" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import ModuleGrid from '@/components/modules/ModuleGrid.vue'

const router = useRouter()
const sessionStore = useSessionStore()
const organelle = ref<'mito' | 'chloro'>('mito')

async function onAiPrompt(prompt: string): Promise<void> {
  if (!sessionStore.activeSessionId) {
    await sessionStore.createSession()
  }
  router.push({ path: `/chat/${sessionStore.activeSessionId}`, query: { prompt } })
}
</script>

<style scoped>
.tools-view { padding: 1.5rem; height: 100%; overflow: auto; }
.tools-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.25rem; }
.tab {
  padding: 0.5rem 1.25rem; border-radius: 0.625rem;
  border: 1px solid var(--border); background: var(--bg);
  color: var(--sub); font-size: 0.875rem; font-weight: 500; cursor: pointer; transition: all 0.15s;
}
.tab:hover { border-color: var(--accent); }
.tab.active { background: var(--accent); color: var(--surface); border-color: var(--accent); }
</style>

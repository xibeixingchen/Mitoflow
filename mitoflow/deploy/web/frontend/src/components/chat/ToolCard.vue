<template>
  <div class="tool-card" :class="{ open: isOpen }">
    <div class="tool-header" @click="toggle">
      <span class="tool-icon">🔧</span>
      <span class="tool-name">{{ name }}</span>
      <span class="tool-toggle">{{ isOpen ? '▼' : '▶' }}</span>
    </div>
    <div v-show="isOpen" class="tool-body">
      <pre>{{ content }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  name: string
  content: string
  open?: boolean
}>()

const isOpen = ref(props.open ?? false)

function toggle() {
  isOpen.value = !isOpen.value
}
</script>

<style scoped>
.tool-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  overflow: hidden;
  margin-bottom: 0.4rem;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.tool-header:hover {
  background: var(--bg);
}

.tool-icon {
  font-size: 0.85rem;
}

.tool-name {
  flex: 1;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text);
}

.tool-toggle {
  font-size: 0.65rem;
  color: var(--sub);
}

.tool-body {
  border-top: 1px solid var(--border);
  max-height: 150px;
  overflow: auto;
}

.tool-body pre {
  margin: 0;
  padding: 0.5rem 0.6rem;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

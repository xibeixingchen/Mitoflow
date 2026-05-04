<template>
  <div
    class="chat-message"
    :class="{ user: role === 'user', assistant: role === 'assistant' }"
    :style="animationStyle"
  >
    <div class="message-bubble" v-html="renderedContent" />
    <div v-if="tools && tools.length" class="tool-results">
      <ToolCard
        v-for="(tool, idx) in tools"
        :key="idx"
        :name="tool.name"
        :content="tool.content"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMarkdown } from '@/composables/useMarkdown'
import ToolCard from './ToolCard.vue'
import type { ToolResult } from '@/types'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  tools?: ToolResult[]
}>()

const { renderMarkdown } = useMarkdown()

const renderedContent = computed(() => renderMarkdown(props.content))

const animationStyle = ref('')

onMounted(() => {
  animationStyle.value = 'animation: fadeIn 0.3s ease forwards;'
})
</script>

<style scoped>
.chat-message {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.chat-message.user {
  align-items: flex-end;
}

.message-bubble {
  max-width: 82%;
  padding: 0.6rem 0.9rem;
  border-radius: 12px;
  line-height: 1.55;
  font-size: 0.85rem;
  word-break: break-word;
}

.chat-message.user .message-bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 3px;
}

.chat-message.assistant .message-bubble {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-bottom-left-radius: 3px;
}

.tool-results {
  margin-top: 0.4rem;
  width: 100%;
  max-width: 82%;
}

:deep(.markdown-table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5rem 0;
  font-size: 0.8rem;
}

:deep(.markdown-table th),
:deep(.markdown-table td) {
  border: 1px solid var(--border);
  padding: 0.35rem 0.5rem;
  text-align: left;
}

:deep(.markdown-table th) {
  background: #f0f4f8;
  font-weight: 600;
}

:deep(code) {
  background: #f0f0f5;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.8em;
}

:deep(pre) {
  background: #f0f0f5;
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0.5rem 0;
}

:deep(pre code) {
  background: none;
  padding: 0;
}

:deep(a) {
  color: var(--accent);
  text-decoration: none;
}

:deep(a:hover) {
  text-decoration: underline;
}

:deep(ul) {
  margin: 0.4rem 0;
  padding-left: 1.2rem;
}

:deep(li) {
  margin: 0.15rem 0;
}
</style>

<template>
  <div class="chat-panel">
    <!-- Welcome Block -->
    <div v-if="!chatStore.hasMessages" class="chat-welcome">
      <div class="welcome-content">
        <h2 class="welcome-title">MitoFlow AI</h2>
        <p class="welcome-subtitle">
          {{ t('chat.placeholder') }}
        </p>
        <div class="suggestions">
          <button
            v-for="(s, i) in suggestions"
            :key="i"
            class="suggestion-chip"
            @click="send(s)"
          >
            {{ s }}
          </button>
        </div>
      </div>
    </div>

    <!-- Message List -->
    <div v-else ref="msgListRef" class="message-list">
      <div
        v-for="(msg, idx) in chatStore.messages"
        :key="idx"
        class="message"
        :class="msg.role"
      >
        <div class="message-avatar">
          {{ msg.role === 'user' ? '👤' : '🤖' }}
        </div>
        <div class="message-body">
          <div class="message-content" v-html="renderMarkdown(msg.content)" />
          <div v-if="msg.tool_calls" class="tool-calls">
            <details>
              <summary>{{ t('chat.toolCalls') }}</summary>
              <pre>{{ JSON.stringify(msg.tool_calls, null, 2) }}</pre>
            </details>
          </div>
        </div>
      </div>

      <div v-if="chatStore.isSending" class="message assistant">
        <div class="message-avatar">🤖</div>
        <div class="message-body">
          <div class="thinking">{{ t('chat.thinking') }}</div>
        </div>
      </div>

      <div v-if="chatStore.error" class="chat-error">
        {{ chatStore.error }}
      </div>
    </div>

    <!-- Input Area -->
    <div class="chat-input-area">
      <textarea
        v-model="inputText"
        class="chat-input"
        rows="1"
        :placeholder="t('chat.placeholder')"
        @keydown.enter.prevent="onEnter"
        @input="autoResize"
      />
      <button
        class="send-btn"
        :disabled="!inputText.trim() || chatStore.isSending"
        @click="onSend"
      >
        {{ t('chat.send') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { sendChat } from '@/api/ai'

const props = defineProps<{
  sessionId?: string
}>()

const { t, tm } = useI18n()
const chatStore = useChatStore()
const sessionStore = useSessionStore()
const settings = useSettingsStore()

const inputText = ref('')
const msgListRef = ref<HTMLDivElement | null>(null)

const suggestions = tm('suggestions') as string[]

function renderMarkdown(text: string): string {
  // Minimal markdown: bold, code blocks, inline code
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`{3}[\s\S]*?`{3}/g, (m) => `<pre><code>${escapeHtml(m.slice(3, -3))}</code></pre>`)
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function autoResize(e: Event): void {
  const ta = e.target as HTMLTextAreaElement
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
}

function onEnter(e: KeyboardEvent): void {
  if (!e.shiftKey) {
    onSend()
  } else {
    inputText.value += '\n'
    nextTick(() => autoResize({ target: document.querySelector('.chat-input') } as Event))
  }
}

async function onSend(): Promise<void> {
  const text = inputText.value.trim()
  if (!text || chatStore.isSending) return

  // Ensure we have an active session
  if (!sessionStore.activeSessionId) {
    await sessionStore.createSession()
  }

  inputText.value = ''
  const ta = document.querySelector('.chat-input') as HTMLTextAreaElement
  if (ta) ta.style.height = 'auto'

  chatStore.messages.push({ role: 'user', content: text })
  chatStore.isSending = true
  chatStore.error = null

  try {
    const res = await sendChat({
      session_id: sessionStore.activeSessionId!,
      message: text,
      provider: settings.providerKey || 'deepseek',
      model: settings.model || 'deepseek-chat',
      api_key: settings.apiKeys[settings.providerKey] || undefined,
      base_url: settings.baseUrl || undefined,
    })

    chatStore.messages.push({
      role: 'assistant',
      content: res.final_text,
      tool_calls: res.tool_results
        ? res.tool_results.map((tr) => ({ id: tr.name, name: tr.name, arguments: {} }))
        : undefined,
      tools: res.tool_results,
    })
  } catch (err: any) {
    chatStore.error = err?.message || 'Failed to send'
  } finally {
    chatStore.isSending = false
    scrollToBottom()
  }
}

function send(text: string): void {
  inputText.value = text
  onSend()
}

function scrollToBottom(): void {
  nextTick(() => {
    msgListRef.value?.scrollTo({ top: msgListRef.value.scrollHeight, behavior: 'smooth' })
  })
}

// Mount: select sessionId if provided
onMounted(() => {
  if (props.sessionId) {
    sessionStore.selectSession(props.sessionId)
    chatStore.loadMessages(props.sessionId).catch(() => {
      // ignore load errors
    })
  }
})

watch(() => chatStore.messages.length, scrollToBottom)
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.chat-welcome {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.welcome-content {
  text-align: center;
  max-width: 520px;
}

.welcome-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.5rem;
}

.welcome-subtitle {
  font-size: 0.875rem;
  color: var(--sub);
  margin-bottom: 1.5rem;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.suggestion-chip {
  padding: 0.5rem 0.875rem;
  border-radius: 0.625rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.15s;
}

.suggestion-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message {
  display: flex;
  gap: 0.75rem;
  max-width: 90%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
  background: var(--bg);
}

.message-body {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text);
}

.message.user .message-body {
  background: var(--accent);
  color: var(--surface);
  border-color: var(--accent);
}

.message-content :deep(pre) {
  background: var(--bg);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 0.5rem 0;
}

.message-content :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8125rem;
  background: var(--bg);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
}

.thinking {
  color: var(--sub);
  font-style: italic;
}

.tool-calls {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--sub);
}

.tool-calls pre {
  background: var(--bg);
  padding: 0.5rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin-top: 0.25rem;
}

.chat-error {
  align-self: center;
  padding: 0.75rem 1rem;
  background: color-mix(in srgb, var(--red) 8%, transparent);
  border: 1px solid var(--red);
  border-radius: 0.5rem;
  color: var(--red);
  font-size: 0.8125rem;
}

.chat-input-area {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border);
  background: var(--surface);
}

.chat-input {
  flex: 1;
  padding: 0.625rem 0.875rem;
  border-radius: 0.625rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.875rem;
  resize: none;
  max-height: 200px;
  line-height: 1.5;
}

.chat-input:focus {
  outline: none;
  border-color: var(--accent);
}

.send-btn {
  padding: 0 1.25rem;
  border-radius: 0.625rem;
  border: none;
  background: var(--accent);
  color: var(--surface);
  font-size: 0.875rem;
  cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
}

.send-btn:hover {
  opacity: 0.9;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

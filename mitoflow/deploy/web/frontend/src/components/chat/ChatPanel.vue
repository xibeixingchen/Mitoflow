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
          <div
            v-if="chatStore.toolEvents.length > 0"
            class="tool-status"
          >
            <span
              v-for="(ev, i) in chatStore.toolEvents"
              :key="i"
              :class="['tool-badge', ev.type]"
            >
              {{ ev.type === 'tool_call' ? '🔧' : '✅' }}
              {{ ev.message }}
            </span>
          </div>
          <div v-else class="thinking">{{ t('chat.thinking') }}</div>
        </div>
      </div>

      <div v-if="chatStore.error" class="chat-error">
        {{ chatStore.error }}
      </div>
    </div>

    <!-- Input Area -->
    <div class="chat-input-area">
      <ChatInput
        :loading="chatStore.isSending"
        @send="onSendFromInput"
        @upload="onUpload"
        @tools="toolSelectorOpen = true"
      />
    </div>

    <!-- Tool Selector -->
    <ToolSelector
      :visible="toolSelectorOpen"
      :input-text="inputTextForTools"
      @close="toolSelectorOpen = false"
      @inject="onToolInject"
      @run="onToolRun"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { streamChat } from '@/api/ai'
import { PRESETS } from '@/constants/presets'
import ChatInput from './ChatInput.vue'
import ToolSelector from './ToolSelector.vue'
import type { ToolItem } from './ToolSelector.vue'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const props = defineProps<{
  sessionId?: string
  autoPrompt?: string
}>()

const { t, tm } = useI18n()
const chatStore = useChatStore()
const sessionStore = useSessionStore()
const settings = useSettingsStore()

const msgListRef = ref<HTMLDivElement | null>(null)
const toolSelectorOpen = ref(false)
const inputTextForTools = ref('')

const suggestions = tm('suggestions') as string[]

// Map provider key → protocol + default model from preset
const currentPreset = computed(() => {
  return PRESETS.find((p) => p.key === settings.providerKey) || PRESETS[0]
})
const chatProtocol = computed(() => currentPreset.value.protocol)
const chatModel = computed(() => settings.model || currentPreset.value.models[0] || '')
const chatBaseUrl = computed(() => settings.baseUrl || currentPreset.value.baseUrl || '')

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const PURIFY_CONFIG = {
  ALLOWED_TAGS: ['br', 'strong', 'a', 'code', 'pre', 'span'],
  ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
}

function renderMarkdown(text: string): string {
  if (!text) return ''

  // 1. Extract code blocks and replace with placeholders
  const codeBlocks: { lang: string; code: string }[] = []
  let html = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_match, lang, code) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`
    codeBlocks.push({ lang: lang || '', code })
    return placeholder
  })

  // 2. Escape HTML in non-code text
  html = escapeHtml(html)

  // 3. Apply markdown transforms
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  html = html.replace(/\n/g, '<br>')

  // 4. Restore code blocks with syntax highlighting
  codeBlocks.forEach(({ lang, code }, i) => {
    const trimmed = code.replace(/\n$/, '')
    let highlighted: string
    if (lang && hljs.getLanguage(lang)) {
      highlighted = hljs.highlight(trimmed, { language: lang }).value
    } else {
      highlighted = hljs.highlightAuto(trimmed).value
    }
    html = html.replace(
      `__CODE_BLOCK_${i}__`,
      `<pre><code class="hljs">${highlighted}</code></pre>`
    )
  })

  // 5. Defensive sanitize
  return DOMPurify.sanitize(html, PURIFY_CONFIG)
}

let _abortController: AbortController | null = null

async function doSend(text: string): Promise<void> {
  if (!text || chatStore.isSending) return

  if (!sessionStore.activeSessionId) {
    await sessionStore.createSession()
  }

  // Push user message
  chatStore.messages.push({ role: 'user', content: text })
  chatStore.isSending = true
  chatStore.error = null
  chatStore.events = []

  // Push empty assistant message (filled incrementally)
  const assistantMsg = { role: 'assistant' as const, content: '', tool_calls: undefined as any }
  chatStore.messages.push(assistantMsg)

  // Cancel previous stream if any
  if (_abortController) _abortController.abort()

  _abortController = streamChat(
    {
      session_id: sessionStore.activeSessionId!,
      message: text,
      provider: chatProtocol.value,
      model: chatModel.value,
      api_key: settings.apiKeys[settings.providerKey] || undefined,
      base_url: chatBaseUrl.value || undefined,
    },
    // onToken: append to assistant message (typewriter effect)
    (token) => {
      assistantMsg.content += token
      scrollToBottom()
    },
    // onToolCall
    (name, args) => {
      chatStore.events.push({ type: 'tool_call', message: `Calling ${name}`, data: { name, arguments: args } })
    },
    // onToolResult
    (name, content, ok) => {
      chatStore.events.push({ type: 'tool_result', message: ok ? content.slice(0, 100) : `Failed: ${content}`, data: { name, ok } })
    },
    // onDone
    (finalText) => {
      if (!assistantMsg.content) assistantMsg.content = finalText
      chatStore.isSending = false
      scrollToBottom()
    },
    // onError
    (msg) => {
      chatStore.error = msg
      chatStore.isSending = false
    },
  )
}

function onSendFromInput(text: string): void {
  doSend(text)
}

function send(text: string): void {
  doSend(text)
}

function onUpload(): void {
  // Navigate to files page or trigger upload dialog
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = () => {
    // TODO: integrate with file store
    const files = Array.from(input.files || [])
    if (files.length) {
      const names = files.map((f) => f.name).join(', ')
      doSend(`Uploading files: ${names}`)
    }
  }
  input.click()
}

function onToolInject(tools: ToolItem[]): void {
  const prompts = tools.map((t) => `[${t.label}]\n${t.prompt}`).join('\n\n')
  inputTextForTools.value = prompts
  // The injected prompts are stored; user can see them when they open the tool selector again
  // Or we can inject directly into the next message
}

async function onToolRun(tools: ToolItem[], text: string): Promise<void> {
  const prompts = tools.map((t) => `[${t.label}]\n${t.prompt}`).join('\n\n')
  const fullMessage = `${prompts}\n\n${text}`.trim()
  await doSend(fullMessage)
}

function scrollToBottom(): void {
  nextTick(() => {
    msgListRef.value?.scrollTo({ top: msgListRef.value.scrollHeight, behavior: 'smooth' })
  })
}

// Mount: select sessionId if provided, auto-send prompt from tools
onMounted(() => {
  if (props.sessionId) {
    sessionStore.selectSession(props.sessionId)
    chatStore.loadMessages(props.sessionId).catch(() => {
      // ignore load errors
    })
  }
  if (props.autoPrompt) {
    nextTick(() => doSend(props.autoPrompt!))
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

.tool-status {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.tool-badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 0.375rem;
  background: var(--bg);
  color: var(--sub);
}

.tool-badge.tool_call {
  border-left: 3px solid var(--accent);
}

.tool-badge.tool_result {
  border-left: 3px solid color-mix(in srgb, var(--green) 70%, var(--accent));
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
  padding: 0.5rem 0.75rem;
  border-top: 1px solid var(--border);
  background: var(--surface);
}
</style>

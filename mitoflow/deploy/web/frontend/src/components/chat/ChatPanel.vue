<template>
  <div class="chat-panel">
    <div ref="messagesContainer" class="messages-area">
      <WelcomeBlock
        v-if="!chatStore.hasMessages"
        @select="onSuggestionSelect"
      />
      <template v-else>
        <div
          v-for="(msg, index) in chatStore.messages"
          :key="index"
          class="message-wrapper"
        >
          <ChatMessage
            :role="msg.role"
            :content="msg.content"
            :tools="msg.tools"
          />
          <ThinkingBar
            v-if="msg.role === 'user' && isLastUserMessage(index) && chatStore.isSending"
            status="thinking"
          />
        </div>
      </template>
    </div>
    <div class="input-area">
      <ChatInput
        :loading="chatStore.isSending"
        @send="onSend"
        @upload="onUpload"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import ChatMessage from './ChatMessage.vue'
import ChatInput from './ChatInput.vue'
import WelcomeBlock from './WelcomeBlock.vue'
import ThinkingBar from './ThinkingBar.vue'

const chatStore = useChatStore()
const sessionStore = useSessionStore()

const messagesContainer = ref<HTMLDivElement | null>(null)

function isLastUserMessage(index: number): boolean {
  for (let i = chatStore.messages.length - 1; i >= 0; i--) {
    if (chatStore.messages[i].role === 'user') {
      return i === index
    }
  }
  return false
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, scrollToBottom, { flush: 'post' })

async function onSend(text: string) {
  if (!sessionStore.activeSession) {
    await sessionStore.createSession()
  }
  await chatStore.sendMessage(text)
}

function onUpload() {
  // Upload handled by parent or file store
}

function onSuggestionSelect(text: string) {
  onSend(text)
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.input-area {
  border-top: 1px solid var(--border);
  padding: 0.75rem 1rem;
  background: var(--surface);
}

.message-wrapper {
  display: flex;
  flex-direction: column;
}
</style>

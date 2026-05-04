<template>
  <div class="chat-input">
    <button
      class="upload-btn"
      type="button"
      :disabled="loading"
      @click="emit('upload')"
    >
      📎
    </button>
    <textarea
      ref="textareaRef"
      v-model="text"
      :placeholder="t('chatPlaceholder')"
      :disabled="loading"
      rows="1"
      @keydown="onKeydown"
      @input="onInput"
    />
    <button
      class="send-btn"
      type="button"
      :disabled="loading || !text.trim()"
      @click="handleSend"
    >
      ➤
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'send', text: string): void
  (e: 'upload'): void
}>()

const { t } = useI18n()
const text = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function onInput() {
  autoResize()
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = '40px'
  const newHeight = Math.min(el.scrollHeight, 140)
  el.style.height = `${newHeight}px`
}

function handleSend() {
  const trimmed = text.value.trim()
  if (!trimmed || props.loading) return
  emit('send', trimmed)
  text.value = ''
  if (textareaRef.value) {
    textareaRef.value.style.height = '40px'
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

watch(() => props.loading, (val) => {
  if (!val) {
    nextTick(() => textareaRef.value?.focus())
  }
})

function nextTick(fn: () => void) {
  Promise.resolve().then(fn)
}
</script>

<style scoped>
.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.4rem 0.6rem;
}

.upload-btn {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.3rem;
  color: var(--sub);
  opacity: 0.7;
  transition: opacity 0.2s;
}

.upload-btn:hover {
  opacity: 1;
}

.upload-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

textarea {
  flex: 1;
  min-height: 40px;
  max-height: 140px;
  padding: 0.5rem 0.4rem;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 0.85rem;
  line-height: 1.4;
  resize: none;
  outline: none;
}

textarea::placeholder {
  color: var(--sub);
  opacity: 0.6;
}

textarea:disabled {
  opacity: 0.5;
}

.send-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.send-btn:hover {
  opacity: 0.9;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>

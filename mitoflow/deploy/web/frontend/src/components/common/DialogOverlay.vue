<script setup lang="ts">
interface Props {
  visible: boolean
  title?: string
  closable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  closable: true,
})

const emit = defineEmits<{
  close: []
}>()

function onOverlayClick() {
  if (props.closable) {
    emit('close')
  }
}

function onContentClick(e: MouseEvent) {
  e.stopPropagation()
}
</script>

<template>
  <Transition name="fade">
    <div v-if="props.visible" class="dialog-overlay" @click="onOverlayClick">
      <div class="dialog-content" @click="onContentClick">
        <div v-if="props.title || props.closable" class="dialog-header">
          <h3 v-if="props.title" class="dialog-title">{{ props.title }}</h3>
          <button v-if="props.closable" class="dialog-close" @click="emit('close')">×</button>
        </div>
        <div class="dialog-body">
          <slot />
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.dialog-content {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border);
}

.dialog-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text);
}

.dialog-close {
  background: transparent;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 6px;
  transition: background 0.15s ease, color 0.15s ease;
}

.dialog-close:hover {
  background: var(--surface-2, var(--border));
  color: var(--text);
}

.dialog-body {
  padding: 1.25rem;
  overflow: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

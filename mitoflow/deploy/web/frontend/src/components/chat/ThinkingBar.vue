<template>
  <div class="thinking-bar">
    <template v-if="status === 'thinking'">
      <span class="pulse-dot" />
      <span class="thinking-text">{{ t('thinking') }}</span>
    </template>
    <template v-else-if="tools && tools.length">
      <span class="chain-icon">🔗</span>
      <span class="chain-text">{{ toolChain }}</span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  status: 'thinking' | 'done'
  tools?: string[]
}>()

const { t } = useI18n()

const toolChain = computed(() => {
  if (!props.tools || props.tools.length === 0) return ''
  return props.tools.join(' → ')
})
</script>

<style scoped>
.thinking-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.6rem;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--sub);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--blue);
  animation: pulse 1.5s ease-in-out infinite;
}

.thinking-text {
  color: var(--blue);
  font-weight: 500;
}

.chain-icon {
  font-size: 0.8rem;
}

.chain-text {
  color: var(--sub);
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.7rem;
}
</style>

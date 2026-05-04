<template>
  <div class="welcome-block">
    <h2 class="welcome-title">MitoFlow AI</h2>
    <p class="welcome-subtitle">{{ t('welcomeSubtitle') }}</p>
    <div class="suggestion-chips">
      <button
        v-for="(suggestion, idx) in suggestions"
        :key="idx"
        class="chip"
        @click="emit('select', suggestion)"
      >
        {{ suggestion }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const suggestions = computed(() => {
  const raw = t('suggestions')
  if (Array.isArray(raw)) return raw
  // Fallback if i18n returns a string or object
  return [
    t('suggestionAnnotate'),
    t('suggestionVisualize'),
    t('suggestionCompare'),
    t('suggestionPhylo'),
  ].filter(Boolean)
})

const emit = defineEmits<{
  (e: 'select', text: string): void
}>()
</script>

<style scoped>
.welcome-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  gap: 0.75rem;
  padding: 2rem;
}

.welcome-title {
  font-size: 1.75rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-subtitle {
  font-size: 0.9rem;
  color: var(--sub);
  max-width: 400px;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  max-width: 480px;
}

.chip {
  padding: 0.4rem 0.8rem;
  font-size: 0.8rem;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}
</style>

<template>
  <div class="lang-toggle">
    <button
      v-for="l in locales"
      :key="l.key"
      class="lang-btn"
      :class="{ active: current === l.key }"
      @click="setLang(l.key)"
    >
      {{ l.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '@/stores/settings'
import { useLocale } from '@/composables/useLocale'

const { locale } = useI18n()
const settings = useSettingsStore()
const { setLocale } = useLocale()

const current = computed(() => locale.value as 'en' | 'zh')

const locales = [
  { key: 'en' as const, label: 'English' },
  { key: 'zh' as const, label: '中文' },
]

function setLang(key: 'en' | 'zh'): void {
  setLocale(key)
  settings.setLanguage(key)
}
</script>

<style scoped>
.lang-toggle {
  display: flex;
  gap: 0.5rem;
}

.lang-btn {
  padding: 0.375rem 0.875rem;
  border-radius: 0.625rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.15s;
}

.lang-btn:hover {
  border-color: var(--accent);
}

.lang-btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
</style>

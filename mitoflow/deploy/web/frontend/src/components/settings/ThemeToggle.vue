<template>
  <div class="theme-toggle">
    <button
      v-for="theme in THEMES"
      :key="theme.key"
      class="theme-btn"
      :class="{ active: current === theme.key }"
      @click="setTheme(theme.key)"
    >
      <span class="theme-emoji">{{ theme.emoji }}</span>
      <span class="theme-label">{{ theme.label }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useTheme } from '@/composables/useTheme'
import { THEMES, type ThemeKey } from '@/constants/themes'

const settings = useSettingsStore()
const { currentTheme, setTheme } = useTheme()

const current = computed(() => currentTheme.value)

function setThemeWrapper(key: ThemeKey): void {
  setTheme(key)
  settings.setTheme(key)
}
</script>

<style scoped>
.theme-toggle {
  display: flex;
  gap: 0.5rem;
}

.theme-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.875rem;
  border-radius: 0.625rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.15s;
}

.theme-btn:hover {
  border-color: var(--accent);
}

.theme-btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.theme-emoji {
  font-size: 0.875rem;
}

.theme-label {
  white-space: nowrap;
}
</style>

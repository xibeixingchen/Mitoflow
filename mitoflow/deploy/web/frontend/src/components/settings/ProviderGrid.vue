<template>
  <div class="provider-grid">
    <button
      v-for="p in PRESETS"
      :key="p.key"
      class="provider-card"
      :class="{ active: settings.providerKey === p.key }"
      @click="select(p.key)"
    >
      <span class="provider-icon">{{ p.icon }}</span>
      <div class="provider-info">
        <span class="provider-name">{{ p.name }}</span>
        <span class="provider-desc">{{ p.desc }}</span>
      </div>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'
import { PRESETS } from '@/constants/presets'

const settings = useSettingsStore()

function select(key: string): void {
  settings.setProvider(key)
  const preset = PRESETS.find((p) => p.key === key)
  if (preset && preset.models.length > 0) {
    settings.setModel(preset.models[0])
  }
  if (preset?.baseUrl) {
    settings.setBaseUrl(preset.baseUrl)
  }
}
</script>

<style scoped>
.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.5rem;
}

.provider-card {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.625rem;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.provider-card:hover {
  border-color: var(--accent);
}

.provider-card.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}

.provider-icon {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.provider-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.provider-name {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.provider-desc {
  font-size: 0.6875rem;
  color: var(--sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>

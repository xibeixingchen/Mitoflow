<template>
  <div class="settings-view">
    <h1 class="settings-title">{{ t('nav.settings') }}</h1>

    <div class="settings-card">
      <div class="setting-row">
        <label class="setting-label">{{ t('settings.language') }}</label>
        <LangToggle />
      </div>

      <div class="setting-row">
        <label class="setting-label">{{ t('settings.theme') }}</label>
        <ThemeToggle />
      </div>

      <div class="setting-row">
        <label class="setting-label">{{ t('settings.protocol') }}</label>
        <div class="protocol-options">
          <button
            v-for="p in protocols"
            :key="p"
            class="protocol-btn"
            :class="{ active: settings.protocol === p }"
            @click="settings.protocol = p"
          >
            {{ t(`settings.${p}`) }}
          </button>
        </div>
      </div>

      <div class="setting-row">
        <label class="setting-label">{{ t('settings.provider') }}</label>
        <ProviderGrid />
      </div>

      <div class="setting-row">
        <label class="setting-label">{{ t('settings.model') }}</label>
        <select v-model="settings.model" class="model-select">
          <option value="">{{ t('settings.model') }}</option>
          <option
            v-for="m in availableModels"
            :key="m"
            :value="m"
          >
            {{ m }}
          </option>
        </select>
      </div>

      <div class="setting-row">
        <label class="setting-label">{{ t('settings.apiKey') }}</label>
        <div class="api-key-wrap">
          <input
            v-model="apiKeyInput"
            type="password"
            class="api-key-input"
            :placeholder="t('settings.apiKey')"
          />
          <button class="save-key-btn" @click="saveKey">
            Save
          </button>
        </div>
        <p class="setting-help">{{ t('settings.apiKeyHelp') }}</p>
      </div>

      <div class="setting-row">
        <label class="setting-label">{{ t('settings.customEndpoint') }}</label>
        <input
          v-model="settings.baseUrl"
          type="text"
          class="endpoint-input"
          placeholder="https://api.example.com/v1"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '@/stores/settings'
import { PRESETS } from '@/constants/presets'
import LangToggle from '@/components/settings/LangToggle.vue'
import ThemeToggle from '@/components/settings/ThemeToggle.vue'
import ProviderGrid from '@/components/settings/ProviderGrid.vue'

const { t } = useI18n()
const settings = useSettingsStore()

const protocols: Array<'openai' | 'anthropic'> = ['openai', 'anthropic']

const availableModels = computed(() => {
  const preset = PRESETS.find((p) => p.key === settings.providerKey)
  return preset?.models || []
})

const apiKeyInput = ref('')

function saveKey(): void {
  if (settings.providerKey && apiKeyInput.value) {
    settings.saveApiKey(settings.providerKey, apiKeyInput.value)
    apiKeyInput.value = ''
  }
}
</script>

<style scoped>
.settings-view {
  padding: 1.5rem;
  height: 100%;
  overflow: auto;
}

.settings-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 1.25rem;
}

.settings-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1.25rem;
  max-width: 720px;
}

.setting-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border);
}

.setting-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.setting-row:first-child {
  padding-top: 0;
}

.setting-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text);
}

.protocol-options {
  display: flex;
  gap: 0.5rem;
}

.protocol-btn {
  padding: 0.375rem 0.875rem;
  border-radius: 0.625rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.15s;
}

.protocol-btn:hover {
  border-color: var(--accent);
}

.protocol-btn.active {
  background: var(--accent);
  color: var(--surface);
  border-color: var(--accent);
}

.model-select {
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.875rem;
  max-width: 360px;
}

.api-key-wrap {
  display: flex;
  gap: 0.5rem;
  max-width: 480px;
}

.api-key-input,
.endpoint-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.875rem;
}

.save-key-btn {
  padding: 0.5rem 1rem;
  border-radius: 0.625rem;
  border: none;
  background: var(--accent);
  color: var(--surface);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: opacity 0.15s;
}

.save-key-btn:hover {
  opacity: 0.9;
}

.setting-help {
  font-size: 0.75rem;
  color: var(--sub);
}
</style>

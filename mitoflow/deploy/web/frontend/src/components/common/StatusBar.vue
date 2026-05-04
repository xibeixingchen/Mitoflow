<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api/client'

const { t } = useI18n()

const isOnline = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

async function checkHealth() {
  try {
    await apiClient.get('/health', { timeout: 8000 })
    isOnline.value = true
  } catch {
    isOnline.value = false
  }
}

onMounted(() => {
  checkHealth()
  timer = setInterval(checkHealth, 30000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<template>
  <div class="status-bar">
    <span class="status-dot" :class="isOnline ? 'online' : 'offline'" />
    <span class="status-text">{{ isOnline ? t('status.connected') : t('status.offline') }}</span>
  </div>
</template>

<style scoped>
.status-bar {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: var(--muted);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.online {
  background: var(--success, #22c55e);
}

.status-dot.offline {
  background: var(--danger, #ef4444);
}

.status-text {
  white-space: nowrap;
}
</style>

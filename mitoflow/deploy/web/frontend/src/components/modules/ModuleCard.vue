<script setup lang="ts">
interface Props {
  icon: string
  name: string
  desc: string
  badge?: 'job' | 'read'
}

const props = defineProps<Props>()
const emit = defineEmits<{
  runAI: []
  runManual: []
  viewResults: []
}>()

const badgeText = {
  job: 'launches job',
  read: 'read only',
}
</script>

<template>
  <div class="module-card">
    <div class="card-header">
      <span class="icon">{{ props.icon }}</span>
      <span v-if="props.badge" class="badge" :class="props.badge">{{ badgeText[props.badge] }}</span>
    </div>
    <h3 class="name">{{ props.name }}</h3>
    <p class="desc">{{ props.desc }}</p>
    <div class="actions">
      <button class="btn-ai" @click="emit('runAI')">🤖 AI Auto</button>
      <button class="btn-manual" @click="emit('runManual')">🔧 Manual</button>
      <button class="btn-results" @click="emit('viewResults')">📊 Results</button>
    </div>
  </div>
</template>

<style scoped>
.module-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.25rem;
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.module-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.icon {
  font-size: 2rem;
  line-height: 1;
}

.badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 9999px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.badge.job {
  background: var(--accent-light, rgba(16, 185, 129, 0.12));
  color: var(--accent);
}

.badge.read {
  background: var(--muted-light, rgba(100, 116, 139, 0.12));
  color: var(--muted);
}

.name {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
  margin: 0;
}

.desc {
  font-size: 0.85rem;
  color: var(--muted);
  line-height: 1.4;
  margin: 0;
  flex: 1;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.actions button {
  border: none;
  border-radius: 8px;
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.1s ease;
}

.actions button:hover {
  opacity: 0.9;
}

.actions button:active {
  transform: scale(0.97);
}

.btn-ai {
  background: var(--accent);
  color: #fff;
}

.btn-manual {
  background: var(--surface-2, var(--border));
  color: var(--text);
}

.btn-results {
  background: var(--surface-2, var(--border));
  color: var(--text);
}
</style>

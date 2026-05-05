<template>
  <div class="module-grid-page">
    <div class="grid-header">
      <h1 class="grid-title">{{ title }}</h1>
      <p class="grid-subtitle">{{ subtitle }}</p>
    </div>

    <div class="grid">
      <div
        v-for="item in items"
        :key="item.id"
        class="grid-card"
      >
        <div class="card-top" @click="onClick(item)">
          <div class="card-icon">{{ item.icon }}</div>
          <div class="card-body">
            <h3 class="card-title">{{ item.name }}</h3>
            <p class="card-desc">{{ item.desc }}</p>
          </div>
        </div>
        <div v-if="mode === 'modules'" class="card-actions">
          <button class="action-btn ai" @click.stop="onAi(item)">
            <span class="btn-icon">🤖</span>
            <span>AI</span>
          </button>
          <button class="action-btn manual" @click.stop="onManual(item)">
            <span class="btn-icon">🛠️</span>
            <span>{{ t('modules.manual') || 'Manual' }}</span>
          </button>
          <button class="action-btn results" @click.stop="onResults(item)">
            <span class="btn-icon">📋</span>
            <span>{{ t('modules.results') || 'Results' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { MODULES, type ModuleDef } from '@/constants/modules'
import { SKILLS, type SkillDef } from '@/constants/skills'

const props = defineProps<{
  mode: 'modules' | 'skills'
  category?: 'mito' | 'cgas'  // filter modules by organelle category
}>()

const emit = defineEmits<{
  (e: 'aiPrompt', prompt: string): void
}>()

const { t } = useI18n()
const router = useRouter()

const title = computed(() => {
  if (props.category === 'cgas') return '叶绿体分析工具'
  if (props.category === 'mito') return '线粒体分析工具'
  return props.mode === 'modules' ? t('modules.title') : t('skills.title')
})

const subtitle = computed(() =>
  props.mode === 'modules' ? t('modules.subtitle') : t('skills.subtitle')
)

const items = computed<(ModuleDef | SkillDef)[]>(() => {
  const base = props.mode === 'modules' ? MODULES : SKILLS
  if (!props.category || props.mode !== 'modules') return base
  if (props.category === 'mito') return base.filter(m => !('category' in m) || m.category !== 'cgas')
  if (props.category === 'cgas') return base.filter(m => 'category' in m && m.category === 'cgas')
  return base
})

function onClick(item: ModuleDef | SkillDef): void {
  // Skills are informational cards — no navigation needed
}

function onAi(item: ModuleDef | SkillDef): void {
  if ('prompt' in item && item.prompt) {
    emit('aiPrompt', item.prompt)
  }
}

function onManual(item: ModuleDef | SkillDef): void {
  router.push(`/tools/${item.id}`)
}

function onResults(item: ModuleDef | SkillDef): void {
  router.push(`/results?module=${item.id}`)
}
</script>

<style scoped>
.module-grid-page {
  max-width: 1200px;
  margin: 0 auto;
}

.grid-header {
  margin-bottom: 1.5rem;
}

.grid-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.25rem;
}

.grid-subtitle {
  font-size: 0.875rem;
  color: var(--sub);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}

.grid-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1.25rem;
  transition: all 0.15s;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.grid-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--accent) 8%, transparent);
  transform: translateY(-1px);
}

.card-top {
  display: flex;
  gap: 0.875rem;
  cursor: pointer;
}

.card-icon {
  font-size: 1.75rem;
  line-height: 1;
  flex-shrink: 0;
}

.card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text);
}

.card-badge {
  font-size: 0.625rem;
  font-weight: 500;
  padding: 0.125rem 0.375rem;
  border-radius: 0.375rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.card-badge.job {
  background: color-mix(in srgb, var(--green) 12%, transparent);
  color: var(--green);
}

.card-badge.read {
  background: color-mix(in srgb, var(--blue) 12%, transparent);
  color: var(--blue);
}

 .card-actions {
  display: flex;
  gap: 0.375rem;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  padding: 0.375rem 0.5rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn:hover {
  border-color: var(--accent);
  background: var(--surface);
}

.action-btn.ai:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.action-btn.manual:hover {
  border-color: var(--blue);
  color: var(--blue);
}

.action-btn.results:hover {
  border-color: var(--green);
  color: var(--green);
}

.btn-icon {
  font-size: 0.875rem;
}

.card-desc {
  font-size: 0.8125rem;
  color: var(--sub);
  line-height: 1.5;
}
</style>

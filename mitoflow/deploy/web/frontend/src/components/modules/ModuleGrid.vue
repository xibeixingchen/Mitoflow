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
        @click="onClick(item)"
      >
        <div class="card-icon">{{ item.icon }}</div>
        <div class="card-body">
          <div class="card-title-row">
            <h3 class="card-title">{{ item.name }}</h3>
            <span
              v-if="mode === 'modules' && 'badge' in item"
              class="card-badge"
              :class="item.badge"
            >
              {{ item.badge === 'job' ? t('modules.jobBadge') : t('modules.readBadge') }}
            </span>
          </div>
          <p class="card-desc">{{ item.desc }}</p>
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
}>()

const { t } = useI18n()
const router = useRouter()

const title = computed(() =>
  props.mode === 'modules' ? t('modules.title') : t('skills.title')
)

const subtitle = computed(() =>
  props.mode === 'modules' ? t('modules.subtitle') : t('skills.subtitle')
)

const items = computed<(ModuleDef | SkillDef)[]>(() =>
  props.mode === 'modules' ? MODULES : SKILLS
)

function onClick(item: ModuleDef | SkillDef): void {
  if (props.mode === 'modules') {
    router.push(`/tools/${item.id}`)
  } else {
    router.push(`/skills/${item.id}`)
  }
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
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  gap: 0.875rem;
}

.grid-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px rgba(5, 150, 105, 0.08);
  transform: translateY(-1px);
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
  background: rgba(16, 185, 129, 0.12);
  color: var(--green);
}

.card-badge.read {
  background: rgba(59, 130, 246, 0.12);
  color: var(--blue);
}

.card-desc {
  font-size: 0.8125rem;
  color: var(--sub);
  line-height: 1.5;
}
</style>

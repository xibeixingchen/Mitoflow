<template>
  <div class="main-layout">
    <AppNav />

    <AppDrawer
      :open="drawerOpen"
      @update:open="drawerOpen = $event"
      @select="onSelectSession"
      @newSession="onNewSession"
    />

    <div class="main-body" :class="{ 'drawer-open': drawerOpen }">
      <AppToolbar
        :title="pageTitle"
        @toggleDrawer="drawerOpen = !drawerOpen"
        @toggleResults="resultsOpen = !resultsOpen"
      />

      <div class="main-content">
        <div class="center-pane" :class="{ 'results-open': showResultsPanel && resultsOpen }">
          <router-view />
        </div>

        <ResultsPanel
          v-if="showResultsPanel"
          :open="resultsOpen"
          active-tab="files"
          @update:open="resultsOpen = $event"
          @switchTab="onSwitchTab"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppNav from './AppNav.vue'
import AppDrawer from './AppDrawer.vue'
import AppToolbar from './AppToolbar.vue'
import ResultsPanel from './ResultsPanel.vue'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const sessionStore = useSessionStore()

const drawerOpen = ref(true)
const resultsOpen = ref(true)

const pageTitle = computed(() => {
  const path = route.path
  if (path.startsWith('/chat')) return t('nav.chat')
  if (path.startsWith('/tools')) return t('nav.tools')
  if (path.startsWith('/skills')) return t('nav.skills')
  if (path.startsWith('/files')) return t('nav.files')
  if (path.startsWith('/results')) return t('nav.results')
  if (path.startsWith('/settings')) return t('nav.settings')
  if (path.startsWith('/account')) return t('nav.account')
  return 'MitoFlow'
})

const showResultsPanel = computed(() => {
  const path = route.path
  return path.startsWith('/chat') || path.startsWith('/tools')
})

function onSelectSession(id: string): void {
  sessionStore.selectSession(id)
  router.push(`/chat/${id}`)
}

async function onNewSession(): Promise<void> {
  const session = await sessionStore.createSession()
  drawerOpen.value = false
  router.push(`/chat/${session.id}`)
}

function onSwitchTab(tab: string): void {
  // eslint-disable-next-line no-console
  console.log('Switch results tab to', tab)
}
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.main-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: var(--nav-w);
  transition: margin-left 0.25s ease;
  overflow: hidden;
}

.main-body.drawer-open {
  margin-left: calc(var(--nav-w) + var(--drawer-w));
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.center-pane {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  transition: margin-right 0.25s ease;
}

.center-pane.results-open {
  margin-right: var(--results-w);
}

/* Mobile responsive */
@media (max-width: 768px) {
  .main-body {
    margin-left: 0;
  }
  .main-body.drawer-open {
    margin-left: 0;
  }
  .center-pane.results-open {
    margin-right: 0;
  }
}
</style>

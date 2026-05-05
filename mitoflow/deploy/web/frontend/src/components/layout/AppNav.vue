<template>
  <nav class="app-nav" role="navigation" aria-label="Main navigation">
    <div class="nav-top">
      <router-link
        v-for="item in analysisItems"
        :key="item.path"
        :to="item.path"
        class="nav-btn"
        :class="{ active: isActive(item.path) }"
        :title="item.label"
        :aria-label="item.label"
        :aria-current="isActive(item.path) ? 'page' : undefined"
      >
        <span class="nav-icon">{{ item.icon }}</span>
      </router-link>

      <div class="nav-divider" />

      <router-link
        v-for="item in configItems"
        :key="item.path"
        :to="item.path"
        class="nav-btn"
        :class="{ active: isActive(item.path) }"
        :title="item.label"
        :aria-label="item.label"
        :aria-current="isActive(item.path) ? 'page' : undefined"
      >
        <span class="nav-icon">{{ item.icon }}</span>
      </router-link>
    </div>

    <div class="nav-bottom">
      <button
        class="nav-btn avatar-btn"
        :title="auth.user?.username || 'User'"
        :aria-label="`User menu for ${auth.user?.username || 'User'}`"
        :aria-expanded="showUserMenu"
        aria-haspopup="dialog"
        @click="showUserMenu = true"
      >
        <span class="avatar-letter">{{ avatarLetter }}</span>
      </button>
    </div>

    <!-- User Menu Dialog -->
    <div
      v-if="showUserMenu"
      class="user-menu-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="User menu"
      @click="showUserMenu = false"
    >
      <div class="user-menu" @click.stop>
        <div class="user-info">
          <span class="user-avatar">{{ avatarLetter }}</span>
          <div class="user-meta">
            <span class="user-name">{{ auth.user?.username || 'User' }}</span>
            <span class="user-email">{{ auth.user?.email || '' }}</span>
          </div>
        </div>
        <div class="menu-divider" />
        <button class="menu-item" @click="onNavigate('/account')">
          <span class="menu-icon">👤</span>
          <span>{{ t('nav.account') }}</span>
        </button>
        <button class="menu-item" @click="onLogout">
          <span class="menu-icon">🚪</span>
          <span>{{ t('auth.logout') }}</span>
        </button>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const auth = useAuthStore()

const showUserMenu = ref(false)

const analysisItems = [
  { path: '/chat', icon: '💬', label: t('nav.chat') },
  { path: '/tools', icon: '🔧', label: t('nav.tools') },
  { path: '/skills', icon: '📋', label: t('nav.skills') },
  { path: '/files', icon: '📤', label: t('nav.files') },
  { path: '/results', icon: '📊', label: t('nav.results') },
]

const configItems = [
  { path: '/settings', icon: '⚙️', label: t('nav.settings') },
  { path: '/account', icon: '👤', label: t('nav.account') },
]

function isActive(path: string): boolean {
  return route.path.startsWith(path)
}

const avatarLetter = computed(() => {
  const name = auth.user?.username || 'U'
  return name.charAt(0).toUpperCase()
})

function onNavigate(path: string): void {
  showUserMenu.value = false
  router.push(path)
}

function onLogout(): void {
  auth.logout()
  showUserMenu.value = false
  router.push('/login')
}
</script>

<style scoped>
.app-nav {
  width: var(--nav-w);
  height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(180deg, var(--nav-grad-1), var(--nav-grad-2));
  padding: 0.5rem 0;
  flex-shrink: 0;
  position: relative;
  z-index: 50;
}

.nav-top,
.nav-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.375rem;
}

.nav-divider {
  width: 24px;
  height: 1px;
  background: color-mix(in srgb, var(--surface) 20%, transparent);
  margin: 0.25rem 0;
}

.nav-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.625rem;
  color: color-mix(in srgb, var(--surface) 70%, transparent);
  text-decoration: none;
  transition: all 0.15s;
  position: relative;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 1.25rem;
}

.nav-btn:hover {
  color: var(--surface);
  background: color-mix(in srgb, var(--surface) 10%, transparent);
}

.nav-btn.active {
  color: var(--text);
  background: var(--surface);
}

.nav-btn.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 24px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}

.avatar-btn {
  background: color-mix(in srgb, var(--surface) 15%, transparent);
  border-radius: 50%;
}

.avatar-letter {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--surface);
}

/* User Menu Dialog */
.user-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
}

.user-menu {
  position: absolute;
  left: calc(var(--nav-w) + 0.5rem);
  bottom: 0.75rem;
  width: 220px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  box-shadow: 0 8px 24px color-mix(in srgb, var(--text) 12%, transparent);
  padding: 0.75rem;
  animation: fadeIn 0.15s ease;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.25rem 0.25rem 0.5rem;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
}

.user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text);
}

.user-email {
  font-size: 0.75rem;
  color: var(--sub);
}

.menu-divider {
  height: 1px;
  background: var(--border);
  margin: 0.5rem 0;
}

.menu-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem;
  border-radius: 0.5rem;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.15s;
}

.menu-item:hover {
  background: var(--bg);
}

.menu-icon {
  font-size: 1rem;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Mobile responsive */
@media (max-width: 768px) {
  .app-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    top: auto;
    width: 100vw;
    height: 52px;
    flex-direction: row;
    justify-content: space-around;
    padding: 0;
    z-index: 110;
    border-top: 1px solid var(--border);
  }
  .nav-top,
  .nav-bottom {
    flex-direction: row;
    gap: 0;
  }
  .nav-divider {
    display: none;
  }
  .nav-btn {
    width: 48px;
    height: 48px;
  }
  .nav-btn.active::before {
    top: auto;
    bottom: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 20px;
    height: 3px;
    border-radius: 2px 2px 0 0;
  }
  .avatar-letter {
    font-size: 0.75rem;
  }
  .user-menu {
    left: auto;
    right: 0.5rem;
    bottom: 60px;
  }
}

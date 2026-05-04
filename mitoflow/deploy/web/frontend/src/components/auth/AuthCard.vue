<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <span class="logo-icon">🧬</span>
        <h1 class="logo-title">MitoFlow AI</h1>
      </div>

      <div class="auth-tabs">
        <button
          class="auth-tab"
          :class="{ active: activeTab === 'login' }"
          @click="activeTab = 'login'"
        >
          {{ t('login') }}
        </button>
        <button
          class="auth-tab"
          :class="{ active: activeTab === 'register' }"
          @click="activeTab = 'register'"
        >
          {{ t('register') }}
        </button>
      </div>

      <div v-if="errorMessage" class="auth-error">
        {{ errorMessage }}
      </div>

      <LoginForm
        v-if="activeTab === 'login'"
        @submit="onLoginSubmit"
        @error="onError"
      />
      <RegisterForm
        v-if="activeTab === 'register'"
        @submit="onRegisterSubmit"
        @error="onError"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import LoginForm from './LoginForm.vue'
import RegisterForm from './RegisterForm.vue'
import type { LoginCredentials, RegisterData } from '@/types'

const { t } = useI18n()

const activeTab = ref<'login' | 'register'>('login')
const errorMessage = ref<string>('')

function onError(msg: string) {
  errorMessage.value = msg
}

function onLoginSubmit(credentials: LoginCredentials) {
  errorMessage.value = ''
  // Parent component handles actual login via auth store
  emit('login', credentials)
}

function onRegisterSubmit(data: RegisterData) {
  errorMessage.value = ''
  // Parent component handles actual registration via auth store
  emit('register', data)
}

const emit = defineEmits<{
  (e: 'login', credentials: LoginCredentials): void
  (e: 'register', data: RegisterData): void
}>()
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--auth-grad-1), var(--auth-grad-2), var(--auth-grad-3));
  padding: 1rem;
}

.auth-card {
  width: 100%;
  max-width: 420px;
  background: var(--surface);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  padding: 2rem;
}

.auth-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.logo-icon {
  font-size: 2rem;
}

.logo-title {
  font-size: 1.5rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.auth-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--border);
}

.auth-tab {
  flex: 1;
  padding: 0.6rem 0;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--sub);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.auth-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.auth-tab:hover {
  color: var(--text);
}

.auth-error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--red);
  padding: 0.6rem 0.8rem;
  border-radius: 8px;
  font-size: 0.8rem;
  margin-bottom: 1rem;
  text-align: center;
}
</style>

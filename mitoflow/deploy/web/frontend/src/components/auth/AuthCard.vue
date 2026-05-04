<template>
  <div class="auth-card">
    <div class="auth-logo">
      <img src="/logo.png" alt="MitoFlow" class="logo-img" />
      <h1 class="logo-text">MitoFlow</h1>
    </div>

    <div class="auth-tabs">
      <button
        class="tab-btn"
        :class="{ active: mode === 'login' }"
        @click="mode = 'login'"
      >
        {{ t('auth.login') }}
      </button>
      <button
        class="tab-btn"
        :class="{ active: mode === 'register' }"
        @click="mode = 'register'"
      >
        {{ t('auth.register') }}
      </button>
    </div>

    <form class="auth-form" @submit.prevent="onSubmit">
      <div v-if="mode === 'register'" class="form-row">
        <label class="form-label">{{ t('auth.username') }}</label>
        <input
          v-model="form.username"
          type="text"
          class="form-input"
          required
        />
      </div>

      <div class="form-row">
        <label class="form-label">{{ t('auth.email') }}</label>
        <input
          v-model="form.email"
          type="email"
          class="form-input"
          required
        />
      </div>

      <div class="form-row">
        <label class="form-label">{{ t('auth.password') }}</label>
        <input
          v-model="form.password"
          type="password"
          class="form-input"
          required
        />
      </div>

      <div v-if="error" class="form-error">{{ error }}</div>

      <button type="submit" class="submit-btn" :disabled="loading">
        {{ loading ? '...' : mode === 'login' ? t('auth.loginBtn') : t('auth.registerBtn') }}
      </button>
    </form>

    <p class="auth-switch">
      {{ mode === 'login' ? t('auth.noAccount') : t('auth.haveAccount') }}
      <button class="switch-btn" @click="toggleMode">
        {{ mode === 'login' ? t('auth.register') : t('auth.login') }}
      </button>
    </p>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  email: '',
  password: '',
})

function toggleMode(): void {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
}

async function onSubmit(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    if (mode.value === 'login') {
      await auth.login({ username: form.email, password: form.password })
    } else {
      await auth.register({
        username: form.username,
        email: form.email,
        password: form.password,
      })
      mode.value = 'login'
      loading.value = false
      return
    }
    router.push('/')
  } catch (err: any) {
    error.value = err?.response?.data?.detail || t('errors.loginFailed')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-card {
  width: 100%;
  max-width: 380px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 2rem;
  box-shadow: 0 4px 24px color-mix(in srgb, var(--text) 6%, transparent);
}

.auth-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.logo-img {
  width: 48px;
  height: 48px;
}

.logo-text {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
}

.auth-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.tab-btn {
  flex: 1;
  padding: 0.5rem;
  border-radius: 0.625rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--sub);
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn.active {
  background: var(--accent);
  color: var(--surface);
  border-color: var(--accent);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text);
}

.form-input {
  padding: 0.625rem 0.875rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.875rem;
  transition: border-color 0.15s;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
}

.form-error {
  font-size: 0.8125rem;
  color: var(--red);
}

.submit-btn {
  padding: 0.625rem;
  border-radius: 0.625rem;
  border: none;
  background: var(--accent);
  color: var(--surface);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}

.submit-btn:hover {
  opacity: 0.9;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.auth-switch {
  margin-top: 1rem;
  text-align: center;
  font-size: 0.8125rem;
  color: var(--sub);
}

.switch-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 0.8125rem;
  padding: 0;
}

.switch-btn:hover {
  text-decoration: underline;
}
</style>

<template>
  <div class="auth-card">
    <div class="auth-logo">
      <img src="/logo.png" alt="MitoFlow" class="logo-img" />
      <h1 class="logo-text">MitoFlow</h1>
    </div>

    <div class="auth-tabs" role="tablist" aria-label="Authentication tabs">
      <button
        class="tab-btn"
        role="tab"
        :class="{ active: mode === 'login' }"
        :aria-selected="mode === 'login'"
        @click="switchMode('login')"
      >
        {{ t('auth.login') }}
      </button>
      <button
        class="tab-btn"
        role="tab"
        :class="{ active: mode === 'register' }"
        :aria-selected="mode === 'register'"
        @click="switchMode('register')"
      >
        {{ t('auth.register') }}
      </button>
    </div>

    <!-- Login Form -->
    <form v-if="mode === 'login'" class="auth-form" role="tabpanel" aria-label="Login" @submit.prevent="onLogin">
      <div class="form-row">
        <label class="form-label" for="login-email">{{ t('auth.email') }}</label>
        <input id="login-email" v-model="form.email" type="email" class="form-input" required />
      </div>
      <div class="form-row">
        <label class="form-label" for="login-password">{{ t('auth.password') }}</label>
        <input id="login-password" v-model="form.password" type="password" class="form-input" required />
      </div>
      <div v-if="error" class="form-error" role="alert" aria-live="assertive">{{ error }}</div>
      <button type="submit" class="submit-btn" :disabled="loading" :aria-busy="loading">
        {{ loading ? '...' : t('auth.loginBtn') }}
      </button>
      <button type="button" class="link-btn" @click="switchMode('forgot')">
        {{ t('auth.forgotPassword') }}
      </button>
    </form>

    <!-- Register Form -->
    <form v-if="mode === 'register'" class="auth-form" role="tabpanel" aria-label="Register" @submit.prevent="onRegister">
      <div class="form-row">
        <label class="form-label" for="reg-username">{{ t('auth.username') }}</label>
        <input id="reg-username" v-model="form.username" type="text" class="form-input" required />
      </div>
      <div class="form-row">
        <label class="form-label" for="reg-email">{{ t('auth.email') }}</label>
        <div class="input-with-btn">
          <input id="reg-email" v-model="form.email" type="email" class="form-input" required />
          <button type="button" class="send-code-btn" :disabled="codeSending || countdown > 0" @click="sendVerifyCode('register')">
            {{ countdown > 0 ? `${countdown}s` : codeSending ? '...' : t('auth.sendCode') }}
          </button>
        </div>
      </div>
      <div class="form-row">
        <label class="form-label" for="reg-code">{{ t('auth.verifyCode') }}</label>
        <input id="reg-code" v-model="form.code" type="text" class="form-input" maxlength="6" placeholder="6-digit code" required />
      </div>
      <div class="form-row">
        <label class="form-label" for="reg-password">{{ t('auth.password') }}</label>
        <input id="reg-password" v-model="form.password" type="password" class="form-input" required minlength="6" />
      </div>
      <div v-if="error" class="form-error" role="alert" aria-live="assertive">{{ error }}</div>
      <div v-if="info" class="form-info" role="status" aria-live="polite">{{ info }}</div>
      <button type="submit" class="submit-btn" :disabled="loading" :aria-busy="loading">
        {{ loading ? '...' : t('auth.registerBtn') }}
      </button>
    </form>

    <!-- Forgot Password Form -->
    <form v-if="mode === 'forgot'" class="auth-form" role="tabpanel" aria-label="Forgot password" @submit.prevent="onForgotSubmit">
      <div class="form-row">
        <label class="form-label" for="forgot-email">{{ t('auth.email') }}</label>
        <div class="input-with-btn">
          <input id="forgot-email" v-model="form.email" type="email" class="form-input" required />
          <button type="button" class="send-code-btn" :disabled="codeSending || countdown > 0" @click="sendVerifyCode('reset_password')">
            {{ countdown > 0 ? `${countdown}s` : codeSending ? '...' : t('auth.sendCode') }}
          </button>
        </div>
      </div>
      <div class="form-row" v-if="codeSent">
        <label class="form-label" for="forgot-code">{{ t('auth.verifyCode') }}</label>
        <input id="forgot-code" v-model="form.code" type="text" class="form-input" maxlength="6" placeholder="6-digit code" required />
      </div>
      <div class="form-row" v-if="codeVerified">
        <label class="form-label" for="forgot-password">{{ t('auth.newPassword') }}</label>
        <input id="forgot-password" v-model="form.password" type="password" class="form-input" required minlength="6" />
      </div>
      <div v-if="error" class="form-error" role="alert" aria-live="assertive">{{ error }}</div>
      <div v-if="info" class="form-info" role="status" aria-live="polite">{{ info }}</div>
      <button type="submit" class="submit-btn" :disabled="loading" :aria-busy="loading">
        {{ loading ? '...' : codeVerified ? t('auth.resetPassword') : codeSent ? 'Verify & Reset' : t('auth.sendCode') }}
      </button>
      <button type="button" class="link-btn" @click="switchMode('login')">
        {{ t('common.back') }}
      </button>
    </form>

    <p class="auth-switch">
      {{ mode === 'login' ? t('auth.noAccount') : t('auth.haveAccount') }}
      <button class="switch-btn" @click="switchMode(mode === 'login' ? 'register' : 'login')">
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
import { apiClient } from '@/api/client'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const mode = ref<'login' | 'register' | 'forgot'>('login')
const loading = ref(false)
const error = ref('')
const info = ref('')
const codeSending = ref(false)
const codeSent = ref(false)
const codeVerified = ref(false)
const devCode = ref('')
const countdown = ref(0)
let _countdownTimer: ReturnType<typeof setInterval> | null = null

function startCountdown(): void {
  countdown.value = 60
  if (_countdownTimer) clearInterval(_countdownTimer)
  _countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      if (_countdownTimer) clearInterval(_countdownTimer)
      _countdownTimer = null
    }
  }, 1000)
}

const form = reactive({
  username: '',
  email: '',
  password: '',
  code: '',
})

function switchMode(m: 'login' | 'register' | 'forgot'): void {
  mode.value = m
  error.value = ''
  info.value = ''
  codeSent.value = false
  codeVerified.value = false
  devCode.value = ''
  countdown.value = 0
  if (_countdownTimer) { clearInterval(_countdownTimer); _countdownTimer = null }
  form.code = ''
  form.password = ''
}

async function sendVerifyCode(purpose: 'register' | 'reset_password'): Promise<void> {
  if (!form.email) { error.value = 'Email required'; return }
  codeSending.value = true
  error.value = ''
  info.value = ''
  try {
    const res = await apiClient.post('/auth/send-code', { email: form.email, purpose })
    codeSent.value = true
    startCountdown()
    if (res.data?.dev_code) {
      devCode.value = res.data.dev_code
      info.value = `DEV: code is ${res.data.dev_code}`
    } else {
      info.value = t('auth.codeSentHint')
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Failed to send code'
  } finally {
    codeSending.value = false
  }
}

async function onLogin(): Promise<void> {
  loading.value = true; error.value = ''
  try {
    await auth.login({ email: form.email, password: form.password })
    router.push('/')
  } catch (err: any) {
    error.value = err?.response?.data?.detail || t('errors.loginFailed')
  } finally { loading.value = false }
}

async function onRegister(): Promise<void> {
  if (!form.code) { error.value = 'Verification code required'; return }
  loading.value = true; error.value = ''
  try {
    await apiClient.post('/auth/register', {
      email: form.email, username: form.username,
      password: form.password, verification_code: form.code,
    })
    await auth.login({ email: form.email, password: form.password })
    router.push('/')
  } catch (err: any) {
    error.value = err?.response?.data?.detail || t('errors.registerFailed')
  } finally { loading.value = false }
}

async function onForgotSubmit(): Promise<void> {
  loading.value = true; error.value = ''
  try {
    if (!codeVerified.value) {
      // Step 1: verify the code
      if (!form.code) { error.value = 'Enter verification code'; return }
      await apiClient.post('/auth/verify-code', { email: form.email, code: form.code, purpose: 'reset_password' })
      codeVerified.value = true
      info.value = 'Code verified. Enter new password.'
    } else {
      // Step 2: reset password using code as token
      if (form.password.length < 6) { error.value = 'Password must be at least 6 characters'; return }
      await apiClient.post('/auth/reset-password', { token: form.code, new_password: form.password })
      info.value = 'Password reset. Redirecting...'
      setTimeout(() => switchMode('login'), 1500)
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Verification failed'
  } finally { loading.value = false }
}
</script>

<style scoped>
.auth-card {
  width: 100%; max-width: 400px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 0.75rem; padding: 2rem;
  box-shadow: 0 4px 24px color-mix(in srgb, var(--text) 6%, transparent);
}
.auth-logo { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; margin-bottom: 1.5rem; }
.logo-img { width: 48px; height: 48px; }
.logo-text { font-size: 1.25rem; font-weight: 700; color: var(--text); }
.auth-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.25rem; }
.tab-btn {
  flex: 1; padding: 0.5rem; border-radius: 0.625rem;
  border: 1px solid var(--border); background: var(--bg);
  color: var(--sub); font-size: 0.875rem; cursor: pointer; transition: all 0.15s;
}
.tab-btn.active { background: var(--accent); color: var(--surface); border-color: var(--accent); }
.auth-form { display: flex; flex-direction: column; gap: 0.875rem; }
.form-row { display: flex; flex-direction: column; gap: 0.25rem; }
.form-label { font-size: 0.8125rem; font-weight: 500; color: var(--text); }
.form-input {
  padding: 0.6rem 0.75rem; border-radius: 0.5rem;
  border: 1px solid var(--border); background: var(--bg);
  color: var(--text); font-size: 0.875rem; transition: border-color 0.15s;
}
.form-input:focus { outline: none; border-color: var(--accent); }
.input-with-btn { display: flex; gap: 0.375rem; }
.input-with-btn .form-input { flex: 1; }
.send-code-btn {
  padding: 0 0.75rem; border-radius: 0.5rem;
  border: 1px solid var(--accent); background: transparent;
  color: var(--accent); font-size: 0.75rem; cursor: pointer; white-space: nowrap;
}
.send-code-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.form-error { font-size: 0.8125rem; color: var(--red); }
.form-info { font-size: 0.75rem; color: var(--green); }
.submit-btn {
  padding: 0.625rem; border-radius: 0.625rem; border: none;
  background: var(--accent); color: var(--surface);
  font-size: 0.875rem; font-weight: 500; cursor: pointer; transition: opacity 0.15s;
}
.submit-btn:hover { opacity: 0.9; }
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.link-btn {
  background: none; border: none; color: var(--accent);
  font-size: 0.8125rem; cursor: pointer; padding: 0; text-align: left;
}
.link-btn:hover { text-decoration: underline; }
.auth-switch { margin-top: 1rem; text-align: center; font-size: 0.8125rem; color: var(--sub); }
.switch-btn { background: none; border: none; color: var(--accent); cursor: pointer; font-size: 0.8125rem; padding: 0; }
.switch-btn:hover { text-decoration: underline; }
</style>

<template>
  <form class="login-form" @submit.prevent="handleSubmit">
    <div class="form-group">
      <label>{{ t('email') }}</label>
      <input
        v-model="email"
        type="email"
        :placeholder="t('emailPlaceholder')"
        required
      />
    </div>
    <div class="form-group">
      <label>{{ t('password') }}</label>
      <input
        v-model="password"
        type="password"
        :placeholder="t('passwordPlaceholder')"
        required
        @keydown.enter="handleSubmit"
      />
    </div>
    <button type="submit" class="login-btn">
      {{ t('login') }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { LoginCredentials } from '@/types'

const { t } = useI18n()

const email = ref('')
const password = ref('')

const emit = defineEmits<{
  (e: 'submit', credentials: LoginCredentials): void
  (e: 'error', msg: string): void
}>()

function handleSubmit() {
  if (!email.value.trim()) {
    emit('error', t('emailRequired'))
    return
  }
  if (!password.value) {
    emit('error', t('passwordRequired'))
    return
  }
  emit('submit', {
    email: email.value.trim(),
    password: password.value,
  })
}
</script>

<style scoped>
.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-group label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--sub);
}

.form-group input {
  padding: 0.6rem 0.8rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--text);
  background: var(--surface);
  transition: border-color 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: var(--accent);
}

.login-btn {
  margin-top: 0.5rem;
  padding: 0.7rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.login-btn:hover {
  opacity: 0.9;
}
</style>

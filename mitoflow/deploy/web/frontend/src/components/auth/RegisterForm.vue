<template>
  <form class="register-form" @submit.prevent="handleSubmit">
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
      <label>{{ t('username') }}</label>
      <input
        v-model="username"
        type="text"
        :placeholder="t('usernamePlaceholder')"
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
      <span v-if="passwordError" class="field-error">{{ passwordError }}</span>
    </div>
    <button type="submit" class="register-btn">
      {{ t('register') }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RegisterData } from '@/types'

const { t } = useI18n()

const email = ref('')
const username = ref('')
const password = ref('')

const passwordError = computed(() => {
  if (password.value && password.value.length < 6) {
    return t('passwordMinLength')
  }
  return ''
})

const emit = defineEmits<{
  (e: 'submit', data: RegisterData): void
  (e: 'error', msg: string): void
}>()

function handleSubmit() {
  if (!email.value.trim()) {
    emit('error', t('emailRequired'))
    return
  }
  if (!username.value.trim()) {
    emit('error', t('usernameRequired'))
    return
  }
  if (!password.value) {
    emit('error', t('passwordRequired'))
    return
  }
  if (password.value.length < 6) {
    emit('error', t('passwordMinLength'))
    return
  }
  emit('submit', {
    email: email.value.trim(),
    username: username.value.trim(),
    password: password.value,
  })
}
</script>

<style scoped>
.register-form {
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

.field-error {
  font-size: 0.75rem;
  color: var(--red);
}

.register-btn {
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

.register-btn:hover {
  opacity: 0.9;
}
</style>

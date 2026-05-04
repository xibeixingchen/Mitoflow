<template>
  <div class="auth-view">
    <AuthCard />
  </div>
</template>

<script setup lang="ts">
import AuthCard from '@/components/auth/AuthCard.vue'
</script>

<style scoped>
.auth-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--auth-grad-1), var(--auth-grad-2), var(--auth-grad-3));
  padding: 1rem;
}
</style>

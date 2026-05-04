<template>
  <div class="chat-view">
    <ChatPanel :session-id="routeSessionId" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ChatPanel from '@/components/chat/ChatPanel.vue'

const route = useRoute()
const routeSessionId = computed<string | undefined>(() => {
  const id = route.params.sessionId
  return typeof id === 'string' ? id : undefined
})
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
</style>

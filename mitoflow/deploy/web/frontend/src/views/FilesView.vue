<template>
  <div class="files-view">
    <UploadZone />
  </div>
</template>

<script setup lang="ts">
import UploadZone from '@/components/files/UploadZone.vue'
</script>

<style scoped>
.files-view {
  padding: 1.5rem;
  height: 100%;
  overflow: auto;
}
</style>

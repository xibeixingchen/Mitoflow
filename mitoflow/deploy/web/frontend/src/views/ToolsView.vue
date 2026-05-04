<template>
  <div class="tools-view">
    <ModuleGrid mode="modules" />
  </div>
</template>

<script setup lang="ts">
import ModuleGrid from '@/components/modules/ModuleGrid.vue'
</script>

<style scoped>
.tools-view {
  padding: 1.5rem;
  height: 100%;
  overflow: auto;
}
</style>

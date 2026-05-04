<template>
  <div class="skills-view">
    <ModuleGrid mode="skills" />
  </div>
</template>

<script setup lang="ts">
import ModuleGrid from '@/components/modules/ModuleGrid.vue'
</script>

<style scoped>
.skills-view {
  padding: 1.5rem;
  height: 100%;
  overflow: auto;
}
</style>

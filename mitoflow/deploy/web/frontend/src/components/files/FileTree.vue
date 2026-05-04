<script setup lang="ts">
import { ref } from 'vue'
import { fileIcon } from '@/utils/fileIcon'

export interface TreeItem {
  name: string
  type: 'file' | 'dir'
  children?: TreeItem[]
}

interface Props {
  items: TreeItem[]
  level?: number
}

const props = withDefaults(defineProps<Props>(), {
  level: 0,
})

const emit = defineEmits<{
  preview: [name: string]
}>()

const expanded = ref<Record<string, boolean>>({})

function toggleDir(name: string) {
  expanded.value[name] = !expanded.value[name]
}

function ext(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i) : ''
}
</script>

<template>
  <ul class="file-tree" :style="{ paddingLeft: props.level ? '1.2rem' : '0' }">
    <li
      v-for="item in props.items"
      :key="item.name"
      class="tree-node"
      :class="item.type"
    >
      <div
        class="node-label"
        @click="item.type === 'dir' ? toggleDir(item.name) : emit('preview', item.name)"
      >
        <span class="node-icon">
          {{ item.type === 'dir' ? (expanded[item.name] ? '📂' : '📁') : fileIcon(ext(item.name)) }}
        </span>
        <span class="node-name">{{ item.name }}</span>
      </div>
      <FileTree
        v-if="item.type === 'dir' && item.children && expanded[item.name]"
        :items="item.children"
        :level="props.level + 1"
        @preview="emit('preview', $event)"
      />
    </li>
  </ul>
</template>

<style scoped>
.file-tree {
  list-style: none;
  margin: 0;
  padding: 0;
}

.tree-node {
  margin: 0.15rem 0;
}

.node-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.4rem;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
  font-size: 0.9rem;
  color: var(--text);
}

.node-label:hover {
  background: var(--surface-2, var(--border));
}

.node-icon {
  font-size: 1rem;
  line-height: 1;
  flex-shrink: 0;
}

.node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

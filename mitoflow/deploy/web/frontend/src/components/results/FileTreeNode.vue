<template>
  <li class="tree-node">
    <div
      class="node-row"
      :class="{ file: node.type === 'file' }"
      @click="onClick"
    >
      <span v-if="node.type === 'dir'" class="node-chevron" :class="{ open: expanded }"
        >▶</span
      >
      <span class="node-icon">{{ node.type === 'dir' ? '📁' : fileIcon(node.name.slice(node.name.lastIndexOf('.'))) }}</span>
      <span class="node-name">{{ node.name }}</span>
    </div>
    <ul v-if="node.type === 'dir' && expanded && node.children" class="node-children">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        @select="$emit('select', $event)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { fileIcon } from '@/utils/fileIcon'
import type { TreeNode } from './FileTree.vue'

const props = defineProps<{
  node: TreeNode
}>()

const emit = defineEmits<{
  (e: 'select', node: TreeNode): void
}>()

const expanded = ref(false)

function onClick(): void {
  if (props.node.type === 'dir') {
    expanded.value = !expanded.value
  } else {
    emit('select', props.node)
  }
}
</script>

<style scoped>
.tree-node {
  user-select: none;
}

.node-row {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.375rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.1s;
}

.node-row:hover {
  background: var(--bg);
}

.node-chevron {
  font-size: 0.5rem;
  color: var(--sub);
  transition: transform 0.15s;
  width: 12px;
  text-align: center;
}

.node-chevron.open {
  transform: rotate(90deg);
}

.node-icon {
  font-size: 0.875rem;
}

.node-name {
  font-size: 0.8125rem;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-children {
  list-style: none;
  padding-left: 1.25rem;
  margin: 0;
}
</style>

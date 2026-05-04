<template>
  <div class="file-tree">
    <div v-if="loading" class="tree-loading">Loading...</div>
    <div v-else-if="tree.length === 0" class="tree-empty">
      No files
    </div>
    <ul v-else class="tree-list">
      <FileTreeNode
        v-for="node in tree"
        :key="node.path"
        :node="node"
        @select="onSelect"
      />
    </ul>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { list } from '@/api/files'
import FileTreeNode from './FileTreeNode.vue'

const sessionStore = useSessionStore()

const loading = ref(false)
const tree = ref<TreeNode[]>([])

export interface TreeNode {
  name: string
  path: string
  type: 'file' | 'dir'
  children?: TreeNode[]
}

const emit = defineEmits<{
  (e: 'select', node: TreeNode): void
}>()

function onSelect(node: TreeNode): void {
  emit('select', node)
}

async function loadTree(): Promise<void> {
  const sessionId = sessionStore.activeSessionId
  if (!sessionId) return
  loading.value = true
  try {
    const res = await list(sessionId)
    tree.value = buildTree(res.files || [])
  } finally {
    loading.value = false
  }
}

function buildTree(files: { name: string; size: number; type: string }[]): TreeNode[] {
  const root: TreeNode[] = []
  for (const f of files) {
    const parts = f.name.split('/')
    let current = root
    let path = ''
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      path = path ? `${path}/${part}` : part
      const existing = current.find((n) => n.name === part)
      if (existing) {
        current = existing.children!
      } else {
        const node: TreeNode = {
          name: part,
          path,
          type: i === parts.length - 1 ? 'file' : 'dir',
          children: i === parts.length - 1 ? undefined : [],
        }
        current.push(node)
        if (node.children) {
          current = node.children
        }
      }
    }
  }
  return root
}

onMounted(() => {
  loadTree()
})
</script>

<style scoped>
.file-tree {
  padding: 0.75rem;
  font-size: 0.8125rem;
}

.tree-loading,
.tree-empty {
  padding: 1rem;
  text-align: center;
  color: var(--sub);
}

.tree-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
</style>

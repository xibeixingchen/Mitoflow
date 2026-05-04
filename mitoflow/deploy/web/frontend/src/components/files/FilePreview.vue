<script setup lang="ts">
interface Props {
  name: string
  content?: string
  url?: string
  type: 'image' | 'text' | 'binary'
}

const props = defineProps<Props>()
</script>

<template>
  <div class="file-preview">
    <div class="preview-header">
      <span class="preview-name">{{ props.name }}</span>
    </div>
    <div class="preview-body">
      <img v-if="props.type === 'image' && props.url" :src="props.url" :alt="props.name" class="preview-image" />
      <pre v-else-if="props.type === 'text' && props.content" class="preview-text">{{ props.content }}</pre>
      <div v-else class="preview-binary">
        <p>Binary file</p>
        <a v-if="props.url" :href="props.url" :download="props.name" class="download-link">Download {{ props.name }}</a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.file-preview {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 80vh;
}

.preview-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2, var(--border));
}

.preview-name {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--text);
}

.preview-body {
  padding: 1rem;
  overflow: auto;
  flex: 1;
}

.preview-image {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  display: block;
}

.preview-text {
  margin: 0;
  padding: 0.75rem;
  background: #f8fafb;
  border-radius: 8px;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow: auto;
  max-height: 65vh;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

.preview-binary {
  text-align: center;
  color: var(--muted);
  padding: 2rem 1rem;
}

.download-link {
  display: inline-block;
  margin-top: 0.75rem;
  padding: 0.4rem 0.9rem;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.85rem;
}

.download-link:hover {
  opacity: 0.9;
}
</style>

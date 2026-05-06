import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  uploadFiles as uploadFilesApi,
  listFiles as listFilesApi,
  deleteFile as deleteFileApi,
  previewFile as previewFileApi,
  downloadFile as downloadFileApi,
} from '@/api/files'
import type { UploadedFile } from '@/types/file'

export const useFileStore = defineStore('file', () => {
  // State
  const files = ref<UploadedFile[]>([])
  const uploading = ref(false)
  const previewFile = ref<{ name: string; content: string; type: string } | null>(null)

  // Actions
  async function uploadFiles(sessionId: string, fileList: File[]) {
    uploading.value = true
    try {
      const res = await uploadFilesApi(sessionId, fileList)
      // Refresh file list after upload so UI shows new files immediately
      await listFiles(sessionId)
      // Notify any open FilePicker to re-fetch
      window.dispatchEvent(new CustomEvent('mitoflow:files-uploaded', { detail: { sessionId } }))
      return res
    } finally {
      uploading.value = false
    }
  }

  async function listFiles(sessionId: string) {
    const resp = await listFilesApi(sessionId)
    files.value = resp.files
  }

  async function deleteFile(name: string, sessionId: string) {
    await deleteFileApi(name, sessionId)
    files.value = files.value.filter((f) => f.name !== name)
    if (previewFile.value?.name === name) {
      previewFile.value = null
    }
  }

  async function previewFileAction(name: string, sessionId: string) {
    // Revoke previous blob URL if it was a blob preview
    if (previewFile.value?.type === 'blob' && previewFile.value.content) {
      window.URL.revokeObjectURL(previewFile.value.content)
    }
    const content = await previewFileApi(name, sessionId)
    previewFile.value = {
      name,
      content,
      type: content.startsWith('blob:') ? 'blob' : 'text',
    }
  }

  async function downloadFile(name: string, sessionId: string) {
    const blob = await downloadFileApi(name, sessionId)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }

  return {
    files,
    uploading,
    previewFile,
    uploadFiles,
    listFiles,
    deleteFile,
    previewFileAction,
    downloadFile,
  }
})

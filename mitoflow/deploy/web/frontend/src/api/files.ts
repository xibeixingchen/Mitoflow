import { apiClient } from './client'
import type { UploadedFile } from '@/types/file'

export interface FileListResponse {
  files: UploadedFile[]
}

export function upload(sessionId: string, files: File[], onProgress?: (pct: number) => void): Promise<FileListResponse> {
  const formData = new FormData()
  formData.append('session_id', sessionId)
  files.forEach((file) => formData.append('files', file))
  return apiClient
    .post('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress
        ? (e) => { if (e.total) onProgress(Math.round((e.loaded / e.total) * 100)) }
        : undefined,
    })
    .then((res) => res.data)
}

export function list(sessionId: string): Promise<FileListResponse> {
  return apiClient
    .get('/files/list', { params: { session_id: sessionId } })
    .then((res) => res.data)
}

export function download(name: string, sessionId: string): Promise<Blob> {
  return apiClient
    .get(`/files/download/${name}`, {
      params: { session_id: sessionId },
      responseType: 'blob',
    })
    .then((res) => res.data)
}

export function deleteFile(name: string, sessionId: string): Promise<void> {
  return apiClient
    .delete(`/files/${name}`, { params: { session_id: sessionId } })
    .then((res) => res.data)
}

export function copyFiles(sourceSessionId: string, targetSessionId: string, filenames: string[]): Promise<{ copied: { name: string; size: number }[]; errors: string[] }> {
  const formData = new FormData()
  formData.append('source_session_id', sourceSessionId)
  formData.append('target_session_id', targetSessionId)
  formData.append('filenames', JSON.stringify(filenames))
  return apiClient
    .post('/files/copy', formData)
    .then((res) => res.data)
}

// Aliases for store compatibility
export const uploadFiles = upload
export const listFiles = list
export const downloadFile = download

let _currentPreviewUrl: string | null = null

export function previewFile(name: string, sessionId: string): Promise<string> {
  const isText = /\.(fasta|fa|fas|fna|gb|gbk|gff|gff3|gtf|txt|csv|tsv|vcf|nwk|treefile|sam|json|xml)$/i.test(name)
  return apiClient
    .get(`/files/download/${name}`, {
      params: { session_id: sessionId },
      responseType: isText ? 'text' : 'blob',
    })
    .then((res) => {
      // Revoke previous preview blob URL to prevent memory leak
      if (_currentPreviewUrl) {
        window.URL.revokeObjectURL(_currentPreviewUrl)
        _currentPreviewUrl = null
      }
      if (res.data instanceof Blob) {
        const url = window.URL.createObjectURL(res.data)
        _currentPreviewUrl = url
        return url
      }
      return res.data as string
    })
}

import { ref } from 'vue'
import { api } from '@/api/client'
import type { ComicDetail } from '@/types'

export interface UploadQueueOptions {
  batchSize?: number
  concurrency?: number
  onProgress?: (completed: number, total: number) => void
}

export function useUploadQueue() {
  const isUploading = ref(false)
  const progress = ref(0)
  const completedCount = ref(0)
  const totalCount = ref(0)
  const currentFileName = ref('')
  const error = ref<string | null>(null)
  let aborted = false

  function cancel() {
    aborted = true
    isUploading.value = false
  }

  async function uploadFiles(
    sourceId: string,
    files: File[],
    chapterId = '',
    newChapterTitle = '',
    options: UploadQueueOptions = {},
  ): Promise<ComicDetail | null> {
    if (files.length === 0) return null

    const batchSize = options.batchSize ?? 15
    const concurrency = options.concurrency ?? 3
    isUploading.value = true
    aborted = false
    error.value = null
    completedCount.value = 0
    totalCount.value = files.length
    progress.value = 0

    // Split files into chunks
    const chunks: File[][] = []
    for (let i = 0; i < files.length; i += batchSize) {
      chunks.push(files.slice(i, i + batchSize))
    }

    let latestDetail: ComicDetail | null = null
    let chunkIndex = 0

    // Worker pool for concurrency
    async function worker(): Promise<void> {
      while (chunkIndex < chunks.length && !aborted) {
        const currentIdx = chunkIndex++
        const chunk = chunks[currentIdx]
        if (!chunk || chunk.length === 0) break

        currentFileName.value = chunk[0]?.name || ''
        try {
          // If first chunk and new chapter title specified, pass it; subsequent chunks append to that chapter
          const targetChap =
            currentIdx === 0
              ? chapterId
              : (latestDetail?.meta.chapters?.slice(-1)[0]?.id ?? chapterId)
          const titleParam = currentIdx === 0 ? newChapterTitle : ''

          const res = await api.uploadLocalPages(sourceId, chunk, targetChap, titleParam)
          latestDetail = res
          completedCount.value = Math.min(totalCount.value, completedCount.value + chunk.length)
          progress.value = Math.round((completedCount.value / totalCount.value) * 100)
          options.onProgress?.(completedCount.value, totalCount.value)
        } catch (err) {
          if (!aborted) {
            error.value = err instanceof Error ? err.message : String(err)
            throw err
          }
        }
      }
    }

    try {
      const workers = Array.from({ length: Math.min(concurrency, chunks.length) }, () => worker())
      await Promise.all(workers)
      progress.value = 100
      return latestDetail
    } finally {
      isUploading.value = false
    }
  }

  return {
    isUploading,
    progress,
    completedCount,
    totalCount,
    currentFileName,
    error,
    cancel,
    uploadFiles,
  }
}

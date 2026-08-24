import { ref } from 'vue'
import { api } from '@/api/client'
import type { ComicDetail } from '@/types'

export interface UploadQueueOptions {
  batchSize?: number
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

    // Ensure files are naturally sorted before batching (e.g. 000.jpg -> 00a.jpg -> 001.jpg)
    const sortedFiles = [...files].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }),
    )

    const batchSize = options.batchSize ?? 25
    isUploading.value = true
    aborted = false
    error.value = null
    completedCount.value = 0
    totalCount.value = sortedFiles.length
    progress.value = 0

    // Split files into sequential chunks
    const chunks: File[][] = []
    for (let i = 0; i < sortedFiles.length; i += batchSize) {
      chunks.push(sortedFiles.slice(i, i + batchSize))
    }

    let latestDetail: ComicDetail | null = null

    try {
      // Process chunks strictly sequentially to preserve 100% stable page ordering
      for (let currentIdx = 0; currentIdx < chunks.length; currentIdx++) {
        if (aborted) break
        const chunk = chunks[currentIdx]
        if (!chunk || chunk.length === 0) continue

        currentFileName.value = chunk[0]?.name || ''

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
      }

      if (!aborted) {
        progress.value = 100
      }
      return latestDetail
    } catch (err) {
      if (!aborted) {
        error.value = err instanceof Error ? err.message : String(err)
        throw err
      }
      return null
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

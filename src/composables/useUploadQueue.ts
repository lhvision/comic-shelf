import { ref } from 'vue'
import { api } from '@/api/client'
import type { ComicDetail } from '@/types'
import { calculateProgressPercent } from '@/utils/progress'

export interface UploadQueueOptions {
  batchSize?: number
  onProgress?: (completed: number, total: number) => void
  source?: string
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

    const source = options.source ?? 'local'

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

    // Detect if this is an auto-split multi-chapter upload (no explicit chapterId, and composite filenames detected across >= 2 chapters)
    const compositeRe =
      /^(?:\[?(?:c|ch|ep|vol|第)?\s*(\d+)\s*(?:话|話|回|卷|期)?\]?)[-_.#\s]+(\d+)/i
    const matchedChapters = new Map<number, File[]>()
    let matchedCount = 0

    for (const f of sortedFiles) {
      const stem = f.name.replace(/\.[^/.]+$/, '')
      const m = compositeRe.exec(stem)
      if (m && m[1]) {
        matchedCount++
        const cnum = parseInt(m[1], 10)
        const list = matchedChapters.get(cnum) ?? []
        list.push(f)
        matchedChapters.set(cnum, list)
      }
    }

    interface UploadBatchTask {
      chunk: File[]
      chapterId: string
      newChapterTitle: string
      isChapterHead: boolean
    }

    const tasks: UploadBatchTask[] = []

    const isCompositeMulti =
      !chapterId &&
      matchedChapters.size > 1 &&
      matchedCount >= Math.max(2, Math.floor(sortedFiles.length * 0.8))

    if (isCompositeMulti) {
      const sortedChapNums = Array.from(matchedChapters.keys()).sort((a, b) => a - b)
      let currChap: number = sortedChapNums[0] ?? 1
      const chapGroupMap = new Map<number, File[]>()
      for (const cnum of sortedChapNums) {
        chapGroupMap.set(cnum, [])
      }
      for (const f of sortedFiles) {
        const stem = f.name.replace(/\.[^/.]+$/, '')
        const m = compositeRe.exec(stem)
        if (m && m[1]) {
          currChap = parseInt(m[1], 10)
        }
        chapGroupMap.get(currChap)?.push(f)
      }

      for (let cIdx = 0; cIdx < sortedChapNums.length; cIdx++) {
        const cnum = sortedChapNums[cIdx]!
        const cFiles = chapGroupMap.get(cnum) || []
        const defaultTitle = `第 ${cnum} 话`
        const titleForChap = cIdx === 0 && newChapterTitle ? newChapterTitle : defaultTitle

        for (let i = 0; i < cFiles.length; i += batchSize) {
          const chunk = cFiles.slice(i, i + batchSize)
          tasks.push({
            chunk,
            chapterId: '',
            newChapterTitle: i === 0 ? titleForChap : '',
            isChapterHead: i === 0,
          })
        }
      }
    } else {
      // Standard sequential chunks
      for (let i = 0; i < sortedFiles.length; i += batchSize) {
        tasks.push({
          chunk: sortedFiles.slice(i, i + batchSize),
          chapterId: i === 0 ? chapterId : '',
          newChapterTitle: i === 0 ? newChapterTitle : '',
          isChapterHead: i === 0,
        })
      }
    }

    let latestDetail: ComicDetail | null = null
    let activeChapterId = chapterId

    try {
      // Process chunks strictly sequentially to preserve 100% stable page ordering
      for (let currentIdx = 0; currentIdx < tasks.length; currentIdx++) {
        if (aborted) break
        const task = tasks[currentIdx]
        if (!task || task.chunk.length === 0) continue

        currentFileName.value = task.chunk[0]?.name || ''

        let targetChap = ''
        let titleParam = ''

        if (isCompositeMulti) {
          if (task.isChapterHead) {
            titleParam = task.newChapterTitle
            targetChap = ''
          } else {
            targetChap = activeChapterId
            titleParam = ''
          }
        } else {
          targetChap =
            currentIdx === 0
              ? chapterId
              : (latestDetail?.meta.chapters?.slice(-1)[0]?.id ?? chapterId)
          titleParam = currentIdx === 0 ? newChapterTitle : ''
        }

        const res = await api.uploadPages(source, sourceId, task.chunk, targetChap, titleParam)
        latestDetail = res
        if (res?.meta?.chapters && res.meta.chapters.length > 0) {
          activeChapterId = res.meta.chapters[res.meta.chapters.length - 1]?.id ?? activeChapterId
        }

        completedCount.value = Math.min(totalCount.value, completedCount.value + task.chunk.length)
        progress.value = calculateProgressPercent(completedCount.value, totalCount.value)
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

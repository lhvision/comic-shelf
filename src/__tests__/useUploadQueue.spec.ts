import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { useUploadQueue } from '@/composables/useUploadQueue'
import { api } from '@/api/client'
import type { ComicDetail } from '@/types'

describe('useUploadQueue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('initializes with default state', () => {
    const queue = useUploadQueue()
    expect(queue.isUploading.value).toBe(false)
    expect(queue.progress.value).toBe(0)
    expect(queue.completedCount.value).toBe(0)
    expect(queue.totalCount.value).toBe(0)
  })

  it('handles empty files gracefully', async () => {
    const queue = useUploadQueue()
    const result = await queue.uploadFiles('test', [])
    expect(result).toBeNull()
    expect(queue.isUploading.value).toBe(false)
  })

  it('uploads files in batches and updates progress', async () => {
    const queue = useUploadQueue()
    const mockFiles = Array.from(
      { length: 5 },
      (_, i) => new File(['dummy'], `frame_${i + 1}.webp`, { type: 'image/webp' }),
    )

    const mockDetail = {
      meta: {
        source: 'local',
        source_id: 'test',
        display_id: 'LOC_test',
        title: 'Test',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        description: '',
        uploader: '自制',
        page_count: 5,
        published_at: '',
        updated_at: '',
        views: '',
        likes: '',
        comment_count: 0,
        favorite: false,
        cover_count: 4,
        source_url: '',
        pages: [],
        imported_at: '',
        last_checked_at: '',
        raw: {},
      },
      cached_pages: 5,
      cache_complete: true,
      cover_paths: [],
    }

    vi.spyOn(api, 'uploadPages').mockResolvedValue(mockDetail)

    const progressUpdates: number[] = []
    const result = await queue.uploadFiles('test', mockFiles, '', '', {
      batchSize: 2,
      onProgress: (completed) => {
        progressUpdates.push(completed)
      },
    })

    expect(result).toEqual(mockDetail)
    expect(queue.progress.value).toBe(100)
    expect(queue.completedCount.value).toBe(5)
    expect(queue.totalCount.value).toBe(5)
    expect(progressUpdates.length).toBeGreaterThan(0)
  })

  it('naturally sorts files before sending (e.g. 000, 00a, 001, 002, 010)', async () => {
    const queue = useUploadQueue()
    const rawNames = ['002.jpg', '000.jpg', '00a.jpg', '010.jpg', '001.jpg']
    const mockFiles = rawNames.map((name) => new File(['dummy'], name, { type: 'image/jpeg' }))

    const uploadedBatches: string[][] = []
    const spy = vi.spyOn(api, 'uploadPages').mockImplementation(async (_src, _id, chunk) => {
      uploadedBatches.push(chunk.map((f) => f.name))
      return {} as unknown as ComicDetail
    })

    await queue.uploadFiles('test', mockFiles, '', '', { batchSize: 10, source: 'picacg' })

    expect(spy).toHaveBeenCalledWith('picacg', 'test', expect.any(Array), '', '')
    expect(uploadedBatches.length).toBe(1)
    expect(uploadedBatches[0]).toEqual(['000.jpg', '00a.jpg', '001.jpg', '002.jpg', '010.jpg'])
  })

  it('correctly groups composite multi-chapter files and sends chapter titles', async () => {
    const queue = useUploadQueue()
    const rawNames = ['1-1.avif', '1-2.avif', '2-1.avif', '2-2.avif']
    const mockFiles = rawNames.map((name) => new File(['dummy'], name, { type: 'image/avif' }))

    const calls: { chunk: string[]; targetChap: string; title: string }[] = []
    let chapterCounter = 0
    vi.spyOn(api, 'uploadPages').mockImplementation(
      async (_src, _id, chunk, targetChap = '', title = '') => {
        calls.push({ chunk: chunk.map((f) => f.name), targetChap, title })
        if (title) chapterCounter++
        return {
          meta: {
            chapters: Array.from({ length: chapterCounter }, (_, i) => ({
              id: `c${i + 1}`,
              index: i + 1,
              title: `第 ${i + 1} 话`,
              page_count: 2,
              start: i * 2 + 1,
            })),
          },
        } as unknown as ComicDetail
      },
    )

    await queue.uploadFiles('test', mockFiles, '', '第 1 话：首章', { batchSize: 2 })

    expect(calls.length).toBe(2)
    // Batch 1: Chapter 1 head
    expect(calls[0]).toEqual({
      chunk: ['1-1.avif', '1-2.avif'],
      targetChap: '',
      title: '第 1 话：首章',
    })
    // Batch 2: Chapter 2 head
    expect(calls[1]).toEqual({
      chunk: ['2-1.avif', '2-2.avif'],
      targetChap: '',
      title: '第 2 话',
    })
  })
})

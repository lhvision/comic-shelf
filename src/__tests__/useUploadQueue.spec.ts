import { describe, it, expect, vi } from 'vite-plus/test'
import { useUploadQueue } from '@/composables/useUploadQueue'
import { api } from '@/api/client'

describe('useUploadQueue', () => {
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

    vi.spyOn(api, 'uploadLocalPages').mockResolvedValue(mockDetail)

    const progressUpdates: number[] = []
    const result = await queue.uploadFiles('test', mockFiles, '', '', {
      batchSize: 2,
      concurrency: 1,
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
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { ref } from 'vue'
import { useChapterCache } from '@/composables/useChapterCache'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { api } from '@/api/client'
import type { CacheJob, Chapter, ComicDetail } from '@/types'

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ toast: vi.fn<() => void>() }),
}))

vi.mock('@/stores/library', () => ({
  useLibraryStore: () => ({
    load: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
  }),
}))

describe('useChapterCache composable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    const { disconnect } = useSystemEvents()
    disconnect()
  })

  const mockChapters: Chapter[] = [
    { id: 'ch-1', index: 1, title: '第 1 话', page_count: 3, start: 1 },
    { id: 'ch-2', index: 2, title: '第 2 话', page_count: 3, start: 4 },
  ]

  function createMockDetail(): ComicDetail {
    return {
      cached_pages: 0,
      cache_complete: false,
      cover_paths: [],
      meta: {
        source: 'jm',
        source_id: '12345',
        display_id: 'JM12345',
        title: '测试漫画',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        description: '',
        uploader: null,
        published_at: '',
        updated_at: '',
        views: '0',
        likes: '0',
        comment_count: 0,
        favorite: false,
        cover_count: 1,
        source_url: '',
        imported_at: '',
        last_checked_at: '',
        raw: {},
        page_count: 6,
        chapters: mockChapters,
        pages: [
          { index: 1, chapter: 'ch-1', file: '01.jpg', ext: 'jpg', cached: false },
          { index: 2, chapter: 'ch-1', file: '02.jpg', ext: 'jpg', cached: false },
          { index: 3, chapter: 'ch-1', file: '03.jpg', ext: 'jpg', cached: false },
          { index: 4, chapter: 'ch-2', file: '04.jpg', ext: 'jpg', cached: false },
          { index: 5, chapter: 'ch-2', file: '05.jpg', ext: 'jpg', cached: false },
          { index: 6, chapter: 'ch-2', file: '06.jpg', ext: 'jpg', cached: false },
        ],
      },
    }
  }

  it('initializes with idle cache state', () => {
    const source = ref('jm')
    const sourceId = ref('12345')
    const detail = ref<ComicDetail | null>(createMockDetail())
    const chapters = ref<Chapter[]>(mockChapters)

    const { caching, runningChapterId } = useChapterCache({
      source,
      sourceId,
      detail,
      chapters,
    })

    expect(caching.value).toBe(false)
    expect(runningChapterId.value).toBeNull()
  })

  it('syncs job state and registers active task when job is running', () => {
    const source = ref('jm')
    const sourceId = ref('12345')
    const detail = ref<ComicDetail | null>(createMockDetail())
    const chapters = ref<Chapter[]>(mockChapters)

    const { caching, runningChapterId, syncJobState } = useChapterCache({
      source,
      sourceId,
      detail,
      chapters,
    })

    const job: CacheJob = {
      running: true,
      done: false,
      source: 'jm',
      source_id: '12345',
      chapter_id: 'ch-1',
      total: 3,
      prefetched: 1,
      warnings: [],
      error: '',
      started_at: 1000,
      finished_at: null,
    }
    syncJobState(job)

    expect(caching.value).toBe(true)
    expect(runningChapterId.value).toBe('ch-1')

    const { hasActiveTasks } = useSystemEvents()
    expect(hasActiveTasks.value).toBe(true)
  })

  it('marks pages correctly in memory', () => {
    const source = ref('jm')
    const sourceId = ref('12345')
    const detail = ref<ComicDetail | null>(createMockDetail())
    const chapters = ref<Chapter[]>(mockChapters)

    const { markPagesCached } = useChapterCache({
      source,
      sourceId,
      detail,
      chapters,
    })

    // Prefetched 2 pages of chapter 1
    markPagesCached({ running: true, chapter_id: 'ch-1', prefetched: 2 })

    const pages = detail.value!.meta.pages
    expect(pages[0]?.cached).toBe(true)
    expect(pages[1]?.cached).toBe(true)
    expect(pages[2]?.cached).toBe(false)
    expect(pages[3]?.cached).toBe(false)

    // Complete chapter 1
    markPagesCached({ running: false, chapter_id: 'ch-1', prefetched: 3 }, true, 'ch-1')
    expect(pages[2]?.cached).toBe(true)
    expect(pages[3]?.cached).toBe(false)

    // Test onPageCached for a single page
    const { onPageCached } = useChapterCache({
      source,
      sourceId,
      detail,
      chapters,
    })
    onPageCached(4)
    expect(pages[3]?.cached).toBe(true)
  })

  it('orchestrates cacheAll lifecycle successfully', async () => {
    const source = ref('jm')
    const sourceId = ref('12345')
    const detail = ref<ComicDetail | null>(createMockDetail())
    const chapters = ref<Chapter[]>(mockChapters)
    const onRefresh = vi.fn<() => void>()

    vi.spyOn(api, 'cacheAll').mockResolvedValueOnce({
      cached: 6,
      total: 6,
      complete: true,
    })

    const { cacheAll, caching } = useChapterCache({
      source,
      sourceId,
      detail,
      chapters,
      onRefresh,
    })

    await cacheAll()

    expect(caching.value).toBe(false)
    expect(detail.value!.cache_complete).toBe(true)
    expect(detail.value!.cached_pages).toBe(6)
    expect(detail.value!.meta.pages.every((p) => p.cached)).toBe(true)
    expect(onRefresh).toHaveBeenCalledTimes(1)
  })

  it('handles partial batch prefetch and maintains active polling when incomplete', async () => {
    const source = ref('jm')
    const sourceId = ref('12345')
    const detail = ref<ComicDetail | null>(createMockDetail())
    const chapters = ref<Chapter[]>(mockChapters)
    const onRefresh = vi.fn<() => void>()

    vi.spyOn(api, 'cacheAll').mockResolvedValueOnce({
      cached: 3,
      total: 6,
      complete: false,
    })

    const { cacheAll, caching } = useChapterCache({
      source,
      sourceId,
      detail,
      chapters,
      onRefresh,
    })

    await cacheAll()

    expect(caching.value).toBe(true)
    expect(detail.value!.cache_complete).toBe(false)
    expect(detail.value!.cached_pages).toBe(3)
  })

  it('orchestrates cacheChapter lifecycle successfully', async () => {
    const source = ref('jm')
    const sourceId = ref('12345')
    const detail = ref<ComicDetail | null>(createMockDetail())
    const chapters = ref<Chapter[]>(mockChapters)
    const onRefresh = vi.fn<() => void>()

    vi.spyOn(api, 'cacheChapter').mockResolvedValueOnce({
      cached: 3,
      total: 3,
      complete: true,
    })

    const { cacheChapter, caching } = useChapterCache({
      source,
      sourceId,
      detail,
      chapters,
      onRefresh,
    })

    await cacheChapter('ch-1')

    expect(caching.value).toBe(false)
    const pages = detail.value!.meta.pages
    expect(pages[0]?.cached).toBe(true)
    expect(pages[1]?.cached).toBe(true)
    expect(pages[2]?.cached).toBe(true)
    expect(pages[3]?.cached).toBe(false)
    expect(onRefresh).toHaveBeenCalledTimes(1)
  })
})

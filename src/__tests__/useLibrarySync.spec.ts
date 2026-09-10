import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { ref, nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useLibrarySync } from '@/composables/useLibrarySync'
import { useLibraryStore } from '@/stores/library'
import type { ReadingStatus, ImageSearchResultItem } from '@/types'
import type { SortKey } from '@/composables/useLibraryFilter'

describe('useLibrarySync composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('restores status and favorite from route query on initialization', () => {
    const route = {
      query: { status: 'reading', favorite: 'true', source: 'jm' },
    } as unknown as Parameters<typeof useLibrarySync>[0]['route']

    const router = {
      replace: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
    } as unknown as Parameters<typeof useLibrarySync>[0]['router']

    const activeSource = ref('jm')
    const search = ref('')
    const activeTag = ref('')
    const favoritesOnly = ref(false)
    const readingStatus = ref<ReadingStatus>('all')
    const sortBy = ref<SortKey>('recent')

    useLibrarySync({
      route,
      router,
      activeSource,
      search,
      activeTag,
      favoritesOnly,
      readingStatus,
      sortBy,
    })

    expect(readingStatus.value).toBe('reading')
    expect(favoritesOnly.value).toBe(true)
  })

  it('synchronizes query parameters and triggers debounced fetch when filters mutate', async () => {
    const store = useLibraryStore()
    const loadItemsSpy = vi.spyOn(store, 'loadItems').mockResolvedValue()
    const loadFacetsSpy = vi.spyOn(store, 'loadFacets').mockResolvedValue()

    const route = { query: {} } as unknown as Parameters<typeof useLibrarySync>[0]['route']
    const replaceMock = vi.fn<(to: unknown) => Promise<void>>().mockResolvedValue(undefined)
    const router = { replace: replaceMock } as unknown as Parameters<
      typeof useLibrarySync
    >[0]['router']

    const activeSource = ref('')
    const search = ref('')
    const activeTag = ref('')
    const favoritesOnly = ref(false)
    const readingStatus = ref<ReadingStatus>('all')
    const sortBy = ref<SortKey>('recent')

    useLibrarySync({
      route,
      router,
      activeSource,
      search,
      activeTag,
      favoritesOnly,
      readingStatus,
      sortBy,
      debounceMs: 100,
    })

    // Mutate filters
    readingStatus.value = 'reading'
    favoritesOnly.value = true
    activeSource.value = 'jm'

    await Promise.resolve()
    expect(replaceMock).toHaveBeenCalledWith({
      query: {
        source: 'jm',
        favorite: 'true',
        status: 'reading',
      },
    })

    // Advance debounce timer
    vi.advanceTimersByTime(150)
    await Promise.resolve()

    expect(loadItemsSpy).toHaveBeenCalledWith(false, false, {
      source: 'jm',
      search: undefined,
      tag: undefined,
      favorite: true,
      status: 'reading',
      sort: 'recent',
      page: 1,
      page_size: 24,
      ids: undefined,
    })
    expect(loadFacetsSpy).toHaveBeenCalledWith('jm')
  })

  it('queries exact matched comics when imageSearchResults are present', async () => {
    const store = useLibraryStore()
    const loadItemsSpy = vi.spyOn(store, 'loadItems').mockResolvedValue()
    const route = { query: {} } as unknown as Parameters<typeof useLibrarySync>[0]['route']
    const router = {
      replace: vi.fn<(to: unknown) => Promise<void>>().mockResolvedValue(undefined),
    } as unknown as Parameters<typeof useLibrarySync>[0]['router']

    const activeSource = ref('')
    const search = ref('')
    const activeTag = ref('')
    const favoritesOnly = ref(false)
    const readingStatus = ref<ReadingStatus>('all')
    const sortBy = ref<SortKey>('recent')
    const imageSearchResults = ref<ImageSearchResultItem[] | null>(null)

    useLibrarySync({
      route,
      router,
      activeSource,
      search,
      activeTag,
      favoritesOnly,
      readingStatus,
      sortBy,
      imageSearchResults,
      debounceMs: 50,
    })

    imageSearchResults.value = [
      { source: 'jm', source_id: '12345', page_index: 2, is_cover: false, score: 0.95 },
      { source: 'jm', source_id: '12345', page_index: 4, is_cover: false, score: 0.88 },
      { source: 'picacg', source_id: '67890', page_index: 1, is_cover: true, score: 0.91 },
    ]

    await nextTick()
    vi.advanceTimersByTime(100)
    await nextTick()

    expect(loadItemsSpy).toHaveBeenCalledWith(false, false, {
      source: undefined,
      search: undefined,
      tag: undefined,
      favorite: undefined,
      status: 'all',
      sort: 'recent',
      page: 1,
      page_size: 24,
      ids: 'jm:12345,picacg:67890',
    })
  })

  it('respects keepLoadedCount when refreshing on route return with existing items', async () => {
    const store = useLibraryStore()
    const loadItemsSpy = vi.spyOn(store, 'loadItems').mockResolvedValue()
    // Simulate store already holding 48 items from previous infinite scrolling
    store.items = Array.from({ length: 48 }, (_, i) => ({
      source: 'jm',
      source_id: `comic_${i}`,
      display_id: `${i}`,
      title: `Comic ${i}`,
      cover_paths: [],
      page_count: 20,
      cached_pages: 0,
      favorite: false,
      authors: [],
      works: [],
      actors: [],
      tags: [],
      views: '0',
      likes: '0',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
      cover_count: 0,
    }))

    const route = { query: {} } as unknown as Parameters<typeof useLibrarySync>[0]['route']
    const router = {
      replace: vi.fn<(to: unknown) => Promise<void>>().mockResolvedValue(undefined),
    } as unknown as Parameters<typeof useLibrarySync>[0]['router']

    const { fetchLibrary } = useLibrarySync({
      route,
      router,
      activeSource: ref(''),
      search: ref(''),
      activeTag: ref(''),
      favoritesOnly: ref(false),
      readingStatus: ref<ReadingStatus>('all'),
      sortBy: ref<SortKey>('recent'),
      debounceMs: 10,
    })

    void fetchLibrary(true, true)
    vi.advanceTimersByTime(20)
    await Promise.resolve()

    // Should query page_size: 48 so the 48 loaded items don't shrink down to 24 on return
    expect(loadItemsSpy).toHaveBeenCalledWith(false, false, {
      source: undefined,
      search: undefined,
      tag: undefined,
      favorite: undefined,
      status: 'all',
      sort: 'recent',
      page: 1,
      page_size: 48,
      ids: undefined,
    })
  })
})

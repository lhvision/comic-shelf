import { describe, expect, it, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useLibraryStore } from '@/stores/library'
import { api } from '@/api/client'
import type { LibraryPageResponse, LibraryFacetsResponse } from '@/types'

describe('useLibraryStore pagination and facets', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads paginated library items and manages hasMore/page states', async () => {
    const mockPage1: LibraryPageResponse = {
      items: [
        {
          source: 'jm',
          source_id: '1',
          display_id: '1',
          title: 'Comic 1',
          authors: [],
          works: [],
          actors: [],
          tags: [],
          favorite: false,
          page_count: 10,
          cached_pages: 5,
          cover_count: 1,
          cover_paths: [],
          views: '0',
          likes: '0',
          uploaded_at: '',
          published_at: '',
          updated_at: '',
          imported_at: '',
        },
      ],
      total: 2,
      page: 1,
      page_size: 1,
      has_more: true,
    }

    const mockPage2: LibraryPageResponse = {
      items: [
        {
          source: 'jm',
          source_id: '2',
          display_id: '2',
          title: 'Comic 2',
          authors: [],
          works: [],
          actors: [],
          tags: [],
          favorite: false,
          page_count: 20,
          cached_pages: 20,
          cover_count: 1,
          cover_paths: [],
          views: '0',
          likes: '0',
          uploaded_at: '',
          published_at: '',
          updated_at: '',
          imported_at: '',
        },
      ],
      total: 2,
      page: 2,
      page_size: 1,
      has_more: false,
    }

    const apiLibrarySpy = vi
      .spyOn(api, 'library')
      .mockResolvedValueOnce(mockPage1)
      .mockResolvedValueOnce(mockPage2)

    const store = useLibraryStore()
    store.pageSize = 1

    await store.loadItems(false, false, { page: 1, page_size: 1, status: 'reading' })
    expect(store.items.length).toBe(1)
    expect(store.items[0]?.source_id).toBe('1')
    expect(store.total).toBe(2)
    expect(store.hasMore).toBe(true)
    expect(store.page).toBe(1)

    // Load next page
    await store.loadMore()
    expect(store.items.length).toBe(2)
    expect(store.items[1]?.source_id).toBe('2')
    expect(store.hasMore).toBe(false)
    expect(store.page).toBe(2)
    expect(apiLibrarySpy).toHaveBeenCalledTimes(2)
  })

  it('loads library facets from api.libraryFacets', async () => {
    const mockFacets: LibraryFacetsResponse = {
      stats: {
        total_books: 120,
        total_pages: 5000,
        cached_pages: 4500,
      },
      top_tags: [
        ['同人', 50],
        ['纯爱', 30],
      ],
    }

    vi.spyOn(api, 'libraryFacets').mockResolvedValue(mockFacets)

    const store = useLibraryStore()
    expect(store.facets).toBeNull()

    await store.loadFacets('jm')
    expect(store.facets).toEqual(mockFacets)
  })

  it('loads all remaining items using store.loadAll()', async () => {
    const mockPage1: LibraryPageResponse = {
      items: [
        {
          source: 'jm',
          source_id: '1',
          display_id: '1',
          title: 'Comic 1',
          authors: [],
          works: [],
          actors: [],
          tags: [],
          favorite: false,
          page_count: 10,
          cached_pages: 5,
          cover_count: 1,
          cover_paths: [],
          views: '0',
          likes: '0',
          uploaded_at: '',
          published_at: '',
          updated_at: '',
          imported_at: '',
        },
      ],
      total: 2,
      page: 1,
      page_size: 1,
      has_more: true,
    }

    const mockRemaining: LibraryPageResponse = {
      items: [
        {
          source: 'jm',
          source_id: '2',
          display_id: '2',
          title: 'Comic 2',
          authors: [],
          works: [],
          actors: [],
          tags: [],
          favorite: false,
          page_count: 20,
          cached_pages: 20,
          cover_count: 1,
          cover_paths: [],
          views: '0',
          likes: '0',
          uploaded_at: '',
          published_at: '',
          updated_at: '',
          imported_at: '',
        },
      ],
      total: 2,
      page: 2,
      page_size: 1,
      has_more: false,
    }

    vi.spyOn(api, 'library').mockResolvedValueOnce(mockPage1).mockResolvedValueOnce(mockRemaining)

    const store = useLibraryStore()
    await store.loadItems(false, false, { page: 1, page_size: 1 })
    expect(store.items.length).toBe(1)
    expect(store.hasMore).toBe(true)

    await store.loadAll()
    expect(store.items.length).toBe(2)
    expect(store.hasMore).toBe(false)
  })
})

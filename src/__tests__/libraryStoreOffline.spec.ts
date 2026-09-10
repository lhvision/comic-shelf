import { describe, expect, it, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useLibraryStore } from '@/stores/library'
import { api } from '@/api/client'
import * as offlineDb from '@/utils/offlineDb'
import type { LibrarySummary } from '@/types'

describe('useLibraryStore offline resilience', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('hydrates items from offline snapshot when initial load is offline', async () => {
    const mockSnapshot: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: '999',
        display_id: '999',
        title: 'Offline Comic',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        page_count: 15,
        cover_count: 1,
        cover_paths: ['/cover.jpg'],
        cached_pages: 15,
        views: '10',
        likes: '2',
        favorite: true,
        hidden_from_guest: false,
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '',
      },
    ]

    vi.spyOn(offlineDb, 'getShelfSnapshot').mockResolvedValue({
      key: 'shelf_default',
      items: mockSnapshot,
      facets: null,
      providers: [],
      timestamp: Date.now(),
    })

    vi.spyOn(api, 'library').mockRejectedValue(new TypeError('Failed to fetch'))
    vi.spyOn(api, 'libraryFacets').mockRejectedValue(new TypeError('Failed to fetch'))

    const store = useLibraryStore()
    await store.load()

    expect(store.items).toHaveLength(1)
    expect(store.items[0]?.title).toBe('Offline Comic')
    expect(store.isOffline).toBe(true)
    expect(store.error).toBe('') // Does not expose loud error when offline snapshot exists
  })

  it('saves shelf snapshot when load succeeds with default status=all params', async () => {
    const mockBooks: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: '123',
        display_id: '123',
        title: 'Online Comic',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        page_count: 10,
        cover_count: 1,
        cover_paths: ['/cover.jpg'],
        cached_pages: 10,
        views: '10',
        likes: '2',
        favorite: false,
        hidden_from_guest: false,
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '',
      },
    ]

    const saveSpy = vi.spyOn(offlineDb, 'saveShelfSnapshot').mockResolvedValue()
    vi.spyOn(api, 'library').mockResolvedValue({
      items: mockBooks,
      total: 1,
      page: 1,
      page_size: 60,
      has_more: false,
    })
    vi.spyOn(api, 'libraryFacets').mockResolvedValue({
      stats: { total_books: 1, total_pages: 10, cached_pages: 10 },
      top_tags: [],
    })

    const store = useLibraryStore()
    await store.load(false, { status: 'all', sort: 'recent' })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(saveSpy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        items: mockBooks,
      }),
    )
  })
})

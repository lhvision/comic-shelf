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

  it('synthesizes items from cached comic details when shelf snapshot is empty', async () => {
    vi.spyOn(offlineDb, 'getShelfSnapshot').mockResolvedValue(null)
    vi.spyOn(offlineDb, 'getAllCachedComicDetails').mockResolvedValue([
      {
        meta: {
          source: 'jm',
          source_id: '628005',
          display_id: 'JM628005',
          title: 'Direct Read Comic',
          authors: ['Artist A'],
          works: [],
          actors: [],
          tags: ['Action'],
          description: '',
          uploader: '',
          page_count: 249,
          cover_count: 1,
          cover_indices: [],
          pages: [],
          views: '500',
          likes: '50',
          comment_count: 0,
          favorite: false,
          hidden_from_guest: false,
          source_url: '',
          published_at: '2026-01-01',
          updated_at: '2026-01-01',
          imported_at: '2026-01-01',
          last_checked_at: '2026-01-01',
          raw: {},
        },
        cached_pages: 249,
        cache_complete: true,
        cover_paths: ['/cover.jpg'],
      },
    ])

    vi.spyOn(api, 'library').mockRejectedValue(new TypeError('Failed to fetch'))
    vi.spyOn(api, 'libraryFacets').mockRejectedValue(new TypeError('Failed to fetch'))

    const store = useLibraryStore()
    await store.load()

    expect(store.items).toHaveLength(1)
    expect(store.items[0]?.title).toBe('Direct Read Comic')
    expect(store.items[0]?.cached_pages).toBe(249)
    expect(store.isOffline).toBe(true)
  })

  it('merges newly read cached details into existing snapshot', async () => {
    const existingSnapshotBook: LibrarySummary = {
      source: 'jm',
      source_id: '100',
      display_id: '100',
      title: 'Existing Shelf Comic',
      authors: [],
      works: [],
      actors: [],
      tags: [],
      page_count: 20,
      cover_count: 1,
      cover_paths: ['/cover.jpg'],
      cached_pages: 20,
      views: '10',
      likes: '2',
      favorite: false,
      hidden_from_guest: false,
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
    }

    vi.spyOn(offlineDb, 'getShelfSnapshot').mockResolvedValue({
      key: 'shelf_default',
      items: [existingSnapshotBook],
      facets: null,
      providers: [],
      timestamp: Date.now(),
    })

    vi.spyOn(offlineDb, 'getAllCachedComicDetails').mockResolvedValue([
      {
        meta: {
          source: 'jm',
          source_id: '200',
          display_id: 'JM200',
          title: 'Newly Read Offline Comic',
          authors: [],
          works: [],
          actors: [],
          tags: [],
          description: '',
          uploader: '',
          page_count: 50,
          cover_count: 1,
          cover_indices: [],
          pages: [],
          views: '0',
          likes: '0',
          comment_count: 0,
          favorite: false,
          hidden_from_guest: false,
          source_url: '',
          published_at: '',
          updated_at: '',
          imported_at: '',
          last_checked_at: '',
          raw: {},
        },
        cached_pages: 50,
        cache_complete: true,
        cover_paths: ['/cover2.jpg'],
      },
    ])

    vi.spyOn(api, 'library').mockRejectedValue(new TypeError('Failed to fetch'))
    vi.spyOn(api, 'libraryFacets').mockRejectedValue(new TypeError('Failed to fetch'))

    const store = useLibraryStore()
    await store.load()

    expect(store.items).toHaveLength(2)
    const titles = store.items.map((i) => i.title)
    expect(titles).toContain('Existing Shelf Comic')
    expect(titles).toContain('Newly Read Offline Comic')
  })

  it('filters out hidden_from_guest items when hydrating offline snapshot for guest users', async () => {
    const publicBook: LibrarySummary = {
      source: 'jm',
      source_id: 'pub-1',
      display_id: 'pub-1',
      title: 'Public Book',
      authors: [],
      works: [],
      actors: [],
      tags: [],
      page_count: 10,
      cover_count: 1,
      cover_paths: ['/cover.jpg'],
      cached_pages: 10,
      views: '0',
      likes: '0',
      favorite: false,
      hidden_from_guest: false,
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
    }

    const hiddenBook: LibrarySummary = {
      source: 'jm',
      source_id: 'priv-1',
      display_id: 'priv-1',
      title: 'Hidden Book',
      authors: [],
      works: [],
      actors: [],
      tags: [],
      page_count: 10,
      cover_count: 1,
      cover_paths: ['/cover.jpg'],
      cached_pages: 10,
      views: '0',
      likes: '0',
      favorite: false,
      hidden_from_guest: true,
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
    }

    vi.spyOn(offlineDb, 'getShelfSnapshot').mockResolvedValue({
      key: 'shelf_guest:user-1',
      items: [publicBook, hiddenBook],
      facets: null,
      providers: [],
      timestamp: Date.now(),
    })

    vi.spyOn(offlineDb, 'getAllCachedComicDetails').mockResolvedValue([
      {
        meta: {
          source: 'jm',
          source_id: 'hidden-detail',
          display_id: 'hidden-detail',
          title: 'Hidden Detail',
          authors: [],
          works: [],
          actors: [],
          tags: [],
          description: '',
          uploader: '',
          page_count: 10,
          cover_count: 1,
          cover_indices: [],
          pages: [],
          views: '0',
          likes: '0',
          comment_count: 0,
          favorite: false,
          hidden_from_guest: true,
          source_url: '',
          published_at: '',
          updated_at: '',
          imported_at: '',
          last_checked_at: '',
          raw: {},
        },
        cached_pages: 10,
        cache_complete: true,
        cover_paths: [],
      },
    ])

    const store = useLibraryStore()
    const result = await store.hydrateFromOfflineSnapshot('guest:user-1')

    expect(result).toBe(true)
    expect(store.items).toHaveLength(1)
    expect(store.items[0]?.source_id).toBe('pub-1')
    expect(store.items.some((i) => i.hidden_from_guest)).toBe(false)
  })
})

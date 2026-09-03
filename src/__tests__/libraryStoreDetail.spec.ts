import { describe, expect, it, beforeEach } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useLibraryStore } from '@/stores/library'
import type { ComicDetail } from '@/types'

function makeMockDetail(sourceId: string): ComicDetail {
  return {
    meta: {
      source: 'jm',
      source_id: sourceId,
      display_id: sourceId,
      title: `Comic ${sourceId}`,
      authors: [],
      works: [],
      actors: [],
      tags: [],
      description: '',
      uploader: null,
      page_count: 10,
      cover_count: 1,
      cover_indices: [],
      pages: [],
      chapters: [],
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
    cached_pages: 0,
    cache_complete: false,
    cover_paths: [],
  }
}

describe('useLibraryStore detailCache', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('stores and retrieves comic details by source and sourceId', () => {
    const store = useLibraryStore()
    const detail = makeMockDetail('123')

    expect(store.getDetail('jm', '123')).toBeUndefined()
    store.setDetail(detail)
    expect(store.getDetail('jm', '123')).toEqual(detail)
  })

  it('removes detail from cache using removeDetail', () => {
    const store = useLibraryStore()
    const detail = makeMockDetail('456')

    store.setDetail(detail)
    expect(store.getDetail('jm', '456')).toBeDefined()

    store.removeDetail('jm', '456')
    expect(store.getDetail('jm', '456')).toBeUndefined()
  })

  it('enforces LRU capacity limit of 20 items', () => {
    const store = useLibraryStore()

    // Insert 25 details
    for (let i = 1; i <= 25; i++) {
      store.setDetail(makeMockDetail(String(i)))
    }

    // Oldest items (1..5) should have been evicted
    for (let i = 1; i <= 5; i++) {
      expect(store.getDetail('jm', String(i))).toBeUndefined()
    }

    // Newest items (6..25) should be present
    for (let i = 6; i <= 25; i++) {
      expect(store.getDetail('jm', String(i))).toBeDefined()
    }
  })
})

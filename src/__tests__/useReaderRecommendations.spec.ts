import { describe, it, expect } from 'vite-plus/test'
import { computeRecommendations } from '@/composables/useReaderRecommendations'
import type { LibrarySummary } from '@/types'

describe('useReaderRecommendations', () => {
  const current = {
    source: 'jm',
    source_id: '100',
    authors: ['Artist Alpha'],
    works: ['Series X'],
    tags: ['Romance', 'School', 'Color'],
  }

  const library: LibrarySummary[] = [
    // Current book itself -> must be excluded
    {
      source: 'jm',
      source_id: '100',
      display_id: '100',
      title: 'Current Comic',
      authors: ['Artist Alpha'],
      works: ['Series X'],
      actors: [],
      tags: ['Romance'],
      favorite: false,
      page_count: 30,
      views: '100',
      likes: '10',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '2026-03-01T00:00:00Z',
      cover_paths: [],
      cached_pages: 30,
      cover_count: 1,
      last_page: 30,
    },
    // Book A: same author + in-progress -> high score
    {
      source: 'jm',
      source_id: '101',
      display_id: '101',
      title: 'Alpha Sequel',
      authors: ['Artist Alpha'],
      works: ['Series Y'],
      actors: [],
      tags: ['School'],
      favorite: false,
      page_count: 40,
      views: '50',
      likes: '5',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '2026-01-01T00:00:00Z',
      cover_paths: [],
      cached_pages: 20,
      cover_count: 1,
      last_page: 15, // in-progress
    },
    // Book B: completed book -> must be excluded!
    {
      source: 'jm',
      source_id: '102',
      display_id: '102',
      title: 'Completed Comic',
      authors: ['Artist Alpha'],
      works: ['Series X'],
      actors: [],
      tags: ['Romance', 'School'],
      favorite: false,
      page_count: 20,
      views: '500',
      likes: '50',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '2026-03-02T00:00:00Z',
      cover_paths: [],
      cached_pages: 20,
      cover_count: 1,
      last_page: 20, // completed
    },
    // Book C: same works + shared tag -> score = 10 + 2 = 12
    {
      source: 'jm',
      source_id: '103',
      display_id: '103',
      title: 'Series X Spin-off',
      authors: ['Artist Beta'],
      works: ['Series X'],
      actors: [],
      tags: ['School'],
      favorite: false,
      page_count: 25,
      views: '30',
      likes: '2',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '2026-02-01T00:00:00Z',
      cover_paths: [],
      cached_pages: 0,
      cover_count: 1,
      last_page: 0, // unread
    },
    // Book D: unread with 1 shared tag -> score = 2
    {
      source: 'jm',
      source_id: '104',
      display_id: '104',
      title: 'Romance Story',
      authors: ['Artist Gamma'],
      works: [],
      actors: [],
      tags: ['Romance'],
      favorite: false,
      page_count: 15,
      views: '10',
      likes: '1',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '2026-02-15T00:00:00Z',
      cover_paths: [],
      cached_pages: 0,
      cover_count: 1,
      last_page: 0, // unread
    },
    // Book E: no matching author/tag, but unread
    {
      source: 'jm',
      source_id: '105',
      display_id: '105',
      title: 'Unrelated Comic',
      authors: ['Artist Delta'],
      works: [],
      actors: [],
      tags: ['Sci-Fi'],
      favorite: false,
      page_count: 50,
      views: '5',
      likes: '0',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '2026-02-20T00:00:00Z',
      cover_paths: [],
      cached_pages: 0,
      cover_count: 1,
      last_page: 0, // unread
    },
  ]

  it('excludes current comic and completed comics, ranking by relevance', () => {
    const recs = computeRecommendations(current, library, 3)

    expect(recs.length).toBe(3)
    // Book 100 (self) and Book 102 (completed) must not appear
    expect(recs.some((b) => b.source_id === '100')).toBe(false)
    expect(recs.some((b) => b.source_id === '102')).toBe(false)

    // Book 101: Author match (10) + Tag match (2) + in-progress (1) = 13
    // Book 103: Work match (10) + Tag match (2) = 12
    // Book 104: Tag match (2) = 2
    expect(recs[0]?.source_id).toBe('101')
    expect(recs[1]?.source_id).toBe('103')
    expect(recs[2]?.source_id).toBe('104')
  })

  it('filters empty strings and whitespace in metadata to avoid false positive matching', () => {
    const currentWithEmpty = {
      source: 'jm',
      source_id: '999',
      authors: ['', '   '],
      works: [''],
      tags: ['  ', ''],
    }

    const testLibrary: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: '888',
        display_id: '888',
        title: 'Empty Meta Comic',
        authors: [''],
        works: ['   '],
        actors: [],
        tags: [''],
        favorite: false,
        page_count: 20,
        views: '10',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-01-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 0,
        cover_count: 1,
        last_page: 0,
      },
    ]

    const recs = computeRecommendations(currentWithEmpty, testLibrary, 1)
    expect(recs.length).toBe(1)
    // Should be returned solely because it is an unread candidate, without receiving false matching score
    expect(recs[0]?.source_id).toBe('888')
  })
})

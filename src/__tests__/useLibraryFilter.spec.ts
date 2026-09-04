import { describe, it, expect } from 'vite-plus/test'
import { useLibraryFilter } from '@/composables/useLibraryFilter'
import { ref } from 'vue'
import type { LibrarySummary, ImageSearchResultItem } from '@/types'

describe('useLibraryFilter', () => {
  const items: LibrarySummary[] = [
    {
      source: 'jm',
      source_id: '1',
      display_id: '1',
      title: 'Book A',
      authors: [],
      works: [],
      actors: [],
      tags: ['tag1'],
      favorite: false,
      page_count: 10,
      views: '0',
      likes: '0',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
      cover_paths: [],
      cached_pages: 10,
      cover_count: 1,
    },
    {
      source: 'jm',
      source_id: '2',
      display_id: '2',
      title: 'Book B',
      authors: [],
      works: [],
      actors: [],
      tags: ['tag2'],
      favorite: false,
      page_count: 20,
      views: '0',
      likes: '0',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
      cover_paths: [],
      cached_pages: 0,
      cover_count: 1,
    },
    {
      source: 'jm',
      source_id: '3',
      display_id: '3',
      title: 'Book C',
      authors: [],
      works: [],
      actors: [],
      tags: ['tag1'],
      favorite: false,
      page_count: 30,
      views: '0',
      likes: '0',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
      cover_paths: [],
      cached_pages: 15,
      cover_count: 1,
    },
  ]

  it('filters and sorts by image search results', () => {
    const itemsRef = ref(items)
    const activeSourceRef = ref('')
    const searchResultsRef = ref<ImageSearchResultItem[]>([
      { source: 'jm', source_id: '2', page_index: 5, score: 0.95, is_cover: false },
      { source: 'jm', source_id: '1', page_index: 1, score: 0.85, is_cover: true },
    ])

    const { filtered, imageSearchMatchMap } = useLibraryFilter(
      itemsRef,
      activeSourceRef,
      searchResultsRef,
    )

    // Should only contain items in search results
    expect(filtered.value.length).toBe(2)
    // Should be sorted by score descending (Book B then Book A)
    expect(filtered.value[0]?.source_id).toBe('2')
    expect(filtered.value[1]?.source_id).toBe('1')

    // Match map correctly built
    expect(imageSearchMatchMap.value.get('jm_2')?.bestScore).toBe(0.95)
    expect(imageSearchMatchMap.value.get('jm_2')?.bestMatchPage).toBe(5)
  })

  it('applies other filters correctly alongside image search', () => {
    const itemsRef = ref(items)
    const activeSourceRef = ref('')
    const searchResultsRef = ref<ImageSearchResultItem[]>([
      { source: 'jm', source_id: '2', page_index: 5, score: 0.95, is_cover: false },
      { source: 'jm', source_id: '1', page_index: 1, score: 0.85, is_cover: true },
    ])

    const { filtered, activeTag } = useLibraryFilter(itemsRef, activeSourceRef, searchResultsRef)

    // apply tag filter
    activeTag.value = 'tag1'

    // Only Book A matches both image search AND tag1
    expect(filtered.value.length).toBe(1)
    expect(filtered.value[0]?.source_id).toBe('1')
  })

  it('deprioritizes completed comics in default recent sort', () => {
    const list: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: '1',
        display_id: '1',
        title: 'Old Unread Book',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        favorite: false,
        page_count: 20,
        views: '0',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-01-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 0,
        cover_count: 1,
        last_page: 0, // 未读
      },
      {
        source: 'jm',
        source_id: '2',
        display_id: '2',
        title: 'Newest Completed Book',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        favorite: false,
        page_count: 10,
        views: '0',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-03-01T00:00:00Z', // 最新添加
        cover_paths: [],
        cached_pages: 10,
        cover_count: 1,
        last_page: 10, // 已读完 (10 >= 10)
      },
      {
        source: 'jm',
        source_id: '3',
        display_id: '3',
        title: 'Mid In-Progress Book',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        favorite: false,
        page_count: 30,
        views: '0',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-02-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 5,
        cover_count: 1,
        last_page: 15, // 在读
      },
    ]

    const itemsRef = ref(list)
    const activeSourceRef = ref('')
    const { filtered, sortBy } = useLibraryFilter(itemsRef, activeSourceRef)

    expect(sortBy.value).toBe('recent')
    // Active (unread + in-progress) sorted by imported_at desc: Book 3 (Feb), then Book 1 (Jan)
    // Completed sunk to the bottom: Book 2 (March, but completed!)
    expect(filtered.value.map((b) => b.source_id)).toEqual(['3', '1', '2'])
  })

  it('filters by completedOnly correctly', () => {
    const list: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: '1',
        display_id: '1',
        title: 'Unread Book',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        favorite: true,
        page_count: 10,
        views: '0',
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
      {
        source: 'jm',
        source_id: '2',
        display_id: '2',
        title: 'Completed Book Favorite',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        favorite: true,
        page_count: 10,
        views: '0',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-02-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 10,
        cover_count: 1,
        last_page: 10,
      },
      {
        source: 'jm',
        source_id: '3',
        display_id: '3',
        title: 'Completed Book Non-Favorite',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        favorite: false,
        page_count: 20,
        views: '0',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-03-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 20,
        cover_count: 1,
        last_page: 20,
      },
    ]

    const itemsRef = ref(list)
    const activeSourceRef = ref('')
    const { filtered, completedOnly, favoritesOnly } = useLibraryFilter(itemsRef, activeSourceRef)

    // Initially all 3
    expect(filtered.value.length).toBe(3)

    // Toggle completed only
    completedOnly.value = true
    expect(filtered.value.map((b) => b.source_id)).toEqual(['3', '2'])

    // Combine completed and favorite
    favoritesOnly.value = true
    expect(filtered.value.map((b) => b.source_id)).toEqual(['2'])

    // Toggle off completed only: Book 1 (unread active) comes before Book 2 (completed)
    completedOnly.value = false
    expect(filtered.value.map((b) => b.source_id)).toEqual(['1', '2'])
  })
})

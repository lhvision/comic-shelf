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

  it('filters by multiple tags using AND intersection logic', () => {
    const multiTagItems: LibrarySummary[] = [
      {
        ...items[0]!,
        source_id: 'm1',
        tags: ['纯爱', '全彩'],
      },
      {
        ...items[1]!,
        source_id: 'm2',
        tags: ['纯爱'],
      },
      {
        ...items[2]!,
        source_id: 'm3',
        tags: ['同人', '全彩'],
      },
    ]

    const itemsRef = ref(multiTagItems)
    const activeSourceRef = ref('')
    const { filtered, activeTags } = useLibraryFilter(itemsRef, activeSourceRef)

    // Select single tag '纯爱' -> m1, m2
    activeTags.value = ['纯爱']
    expect(filtered.value.length).toBe(2)

    // Select multiple tags '纯爱' + '全彩' -> only m1 (AND intersection)
    activeTags.value = ['纯爱', '全彩']
    expect(filtered.value.length).toBe(1)
    expect(filtered.value[0]?.source_id).toBe('m1')

    // Select non-intersecting tags -> 0 matches
    activeTags.value = ['纯爱', '短篇']
    expect(filtered.value.length).toBe(0)
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

  it('filters by readingStatus completed combined with favorites correctly', () => {
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
    const { filtered, readingStatus, favoritesOnly } = useLibraryFilter(itemsRef, activeSourceRef)

    // Initially all 3
    expect(filtered.value.length).toBe(3)

    // Filter by completed status
    readingStatus.value = 'completed'
    expect(filtered.value.map((b) => b.source_id)).toEqual(['3', '2'])

    // Combine completed and favorite
    favoritesOnly.value = true
    expect(filtered.value.map((b) => b.source_id)).toEqual(['2'])

    // Reset readingStatus: Book 1 (unread active) comes before Book 2 (completed)
    readingStatus.value = 'all'
    expect(filtered.value.map((b) => b.source_id)).toEqual(['1', '2'])
  })

  it('filters by readingStatus dimension correctly', () => {
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
        favorite: false,
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
        title: 'In-Progress Book',
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
        imported_at: '2026-02-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 10,
        cover_count: 1,
        last_page: 5,
      },
      {
        source: 'jm',
        source_id: '3',
        display_id: '3',
        title: 'Completed Book',
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
        imported_at: '2026-03-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 30,
        cover_count: 1,
        last_page: 30,
      },
    ]

    const itemsRef = ref(list)
    const activeSourceRef = ref('')
    const { filtered, readingStatus } = useLibraryFilter(itemsRef, activeSourceRef)

    // Default 'all'
    expect(filtered.value.length).toBe(3)

    // Filter 'reading' (in-progress only)
    readingStatus.value = 'reading'
    expect(filtered.value.map((b) => b.source_id)).toEqual(['2'])

    // Filter 'completed'
    readingStatus.value = 'completed'
    expect(filtered.value.map((b) => b.source_id)).toEqual(['3'])

    // Back to 'all'
    readingStatus.value = 'all'
    expect(filtered.value.length).toBe(3)
  })

  it('sorts by cached page completion ratio correctly when requested', () => {
    const itemsRef = ref(items) // Book A (cached 10/10), Book B (cached 0/20), Book C (cached 15/30)
    const activeSourceRef = ref('')
    const { filtered, setSort } = useLibraryFilter(itemsRef, activeSourceRef)

    expect(filtered.value.length).toBe(3)
    setSort('cached')
    expect(filtered.value.map((b) => b.source_id)).toEqual(['1', '3', '2'])
  })

  it('matches chapter titles in search query (T11 specification)', () => {
    const list = [
      {
        source: 'jm',
        source_id: '1',
        display_id: '1',
        title: '长篇冒险故事',
        authors: ['作者A'],
        works: [],
        actors: [],
        tags: ['冒险'],
        favorite: false,
        page_count: 100,
        views: '0',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '',
        cover_paths: [],
        cached_pages: 50,
        cover_count: 1,
        chapter_titles: ['第 1 话 起源', '第 2 话 启程', '第 5 话 迷宫探索'],
      },
      {
        source: 'jm',
        source_id: '2',
        display_id: '2',
        title: '都市日常',
        authors: ['作者B'],
        works: [],
        actors: [],
        tags: ['日常'],
        favorite: false,
        page_count: 50,
        views: '0',
        likes: '0',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '',
        cover_paths: [],
        cached_pages: 20,
        cover_count: 1,
        chapter_titles: ['第 1 话 相遇'],
      },
    ]

    const itemsRef = ref(list)
    const activeSourceRef = ref('')
    const { filtered, search } = useLibraryFilter(itemsRef, activeSourceRef)

    // Searching '第 5 话' should match Book 1 via chapter_titles
    search.value = '第 5 话'
    expect(filtered.value.length).toBe(1)
    expect(filtered.value[0]?.source_id).toBe('1')

    // Searching non-existent chapter
    search.value = '第 99 话'
    expect(filtered.value.length).toBe(0)
  })

  it('sorts titles naturally with numeric awareness (e.g. 2 before 10)', () => {
    const list: LibrarySummary[] = [
      { ...items[0]!, source_id: '10', title: '第 10 卷' },
      { ...items[0]!, source_id: '2', title: '第 2 卷' },
      { ...items[0]!, source_id: '1', title: '第 1 卷' },
    ]
    const itemsRef = ref(list)
    const activeSourceRef = ref('')
    const { filtered, setSort } = useLibraryFilter(itemsRef, activeSourceRef)

    setSort('title')
    expect(filtered.value.map((b) => b.source_id)).toEqual(['1', '2', '10'])
  })

  it('correctly maps filtered items to lightweight ID array via filterAndSortLibraryIds', async () => {
    const { filterAndSortLibraryIds } = await import('@/utils/libraryFilterCore')
    const ids = filterAndSortLibraryIds(items, {
      activeSource: '',
      search: '',
      activeTag: 'tag2',
      favoritesOnly: false,
      readingStatus: 'all',
      sortBy: 'recent',
    })
    expect(ids).toEqual(['jm:2'])
  })

  it('handles large collections (>1000 items) gracefully in node/vitest environment via synchronous fallback', () => {
    // Generate 1200 items
    const largeList: LibrarySummary[] = Array.from({ length: 1200 }, (_, i) => ({
      source: 'jm',
      source_id: String(i + 1),
      display_id: String(i + 1),
      title: `Book ${i + 1}`,
      authors: [`Author ${i % 5}`],
      works: [],
      actors: [],
      tags: [i % 2 === 0 ? 'even' : 'odd'],
      favorite: i % 10 === 0,
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
      last_page: 0,
    }))

    const itemsRef = ref(largeList)
    const activeSourceRef = ref('')
    const { filtered, search, activeTag } = useLibraryFilter(itemsRef, activeSourceRef)

    // Initially all 1200 items in Node environment without Worker support
    expect(filtered.value.length).toBe(1200)

    // Tag filter
    activeTag.value = 'odd'
    expect(filtered.value.length).toBe(600)

    // Search filter
    search.value = 'Book 12'
    // Matches Book 12, Book 121, Book 123, Book 125, Book 127, Book 129, etc.
    expect(filtered.value.length).toBeGreaterThan(0)
    for (const book of filtered.value) {
      expect(book.title).toContain('Book 12')
      expect(book.tags).toContain('odd')
    }
  })

  it('safely handles special regex characters and symbols in search needle without crashing', () => {
    const list: LibrarySummary[] = [
      {
        ...items[0]!,
        source_id: 'special-1',
        title: 'Book [Special] (Vol. 1) + Extras *',
        tags: ['c++'],
      },
      { ...items[1]!, source_id: 'special-2', title: 'Normal Book' },
    ]
    const itemsRef = ref(list)
    const activeSourceRef = ref('')
    const { filtered, search } = useLibraryFilter(itemsRef, activeSourceRef)

    // Regex chars: [ ] ( ) + * ? \
    search.value = '[special]'
    expect(filtered.value.length).toBe(1)
    expect(filtered.value[0]?.source_id).toBe('special-1')

    search.value = '(vol. 1) +'
    expect(filtered.value.length).toBe(1)

    search.value = '*'
    expect(filtered.value.length).toBe(1)

    search.value = 'c++'
    expect(filtered.value.length).toBe(1)
  })

  it('safely ignores null or undefined items in library array without throwing', () => {
    const corruptedList = [
      items[0]!,
      null as unknown as LibrarySummary,
      undefined as unknown as LibrarySummary,
      items[1]!,
    ]
    const itemsRef = ref(corruptedList)
    const activeSourceRef = ref('')
    const { filtered, totalBooks } = useLibraryFilter(itemsRef, activeSourceRef)

    expect(totalBooks.value).toBe(2)
    expect(filtered.value.length).toBe(2)
    expect(filtered.value.map((b) => b.source_id)).toEqual(['1', '2'])
  })
})

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
})

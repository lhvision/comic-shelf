import { describe, it, expect } from 'vite-plus/test'
import { ref } from 'vue'
import { useReaderPaging } from '@/composables/useReaderPaging'
import { DEFAULT_SETTINGS, type ReaderSettings } from '@/composables/useReaderSettings'
import type { ComicDetail } from '@/types'

function createMockDetail(
  pageCount: number,
  chapters?: { id: string; index: number; title: string; page_count: number; start: number }[],
): ComicDetail {
  return {
    meta: {
      source: 'jm',
      source_id: 'test-comic',
      display_id: 'test-comic',
      title: '测试漫画',
      authors: ['测试作者'],
      works: [],
      actors: [],
      tags: [],
      description: '',
      uploader: null,
      page_count: pageCount,
      cover_count: 1,
      cover_indices: [],
      pages: Array.from({ length: pageCount }, (_, i) => ({
        index: i + 1,
        file: `${String(i + 1).padStart(5, '0')}.webp`,
        ext: '.webp',
        cached: false,
      })),
      chapters: chapters ?? [],
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

describe('useReaderPaging - End Card Navigation Integration', () => {
  it('includes End Card as virtual last group in single volume comic', () => {
    const detail = ref<ComicDetail | null>(createMockDetail(10))
    const scopeId = ref<string | null>(null)
    const settings = ref<ReaderSettings>({ ...DEFAULT_SETTINGS, pagesPerView: 2 })
    const currentPage = ref(1)
    const currentGroupIndex = ref(0)

    const paging = useReaderPaging({
      detail,
      scopeId,
      settings,
      currentPage,
      currentGroupIndex,
    })

    // 10 pages / 2 ppv = 5 groups (indices 0..4)
    expect(paging.pageGroups.value.length).toBe(5)
    expect(paging.showEndCard.value).toBe(true)

    // With showEndCard, lastGroupIndex points to group 5 (the virtual End Card)
    expect(paging.lastGroupIndex.value).toBe(5)

    // On the last comic spread (group 4, pages 9-10)
    currentGroupIndex.value = 4
    expect(paging.atLastGroup.value).toBe(false) // Not yet at End Card, user can still click next!
    expect(paging.currentGroupLabel.value).toBe('9–10')
    expect(paging.groupFirstPage(4)).toBe(9)

    // Navigating into End Card (group 5)
    currentGroupIndex.value = 5
    expect(paging.atLastGroup.value).toBe(true) // Reached End Card
    expect(paging.currentGroupLabel.value).toBe('完')
    expect(paging.groupFirstPage(5)).toBe(10) // Returns final page of comic
  })

  it('does NOT include End Card in lastGroupIndex when an intermediate chapter has nextChapter', () => {
    const chapters = [
      { id: 'ch1', index: 1, title: '第 1 话', page_count: 6, start: 1 },
      { id: 'ch2', index: 2, title: '第 2 话', page_count: 6, start: 7 },
    ]
    const detail = ref<ComicDetail | null>(createMockDetail(12, chapters))
    const scopeId = ref<string | null>('ch1')
    const settings = ref<ReaderSettings>({ ...DEFAULT_SETTINGS, pagesPerView: 2 })
    const currentPage = ref(1)
    const currentGroupIndex = ref(0)

    const paging = useReaderPaging({
      detail,
      scopeId,
      settings,
      currentPage,
      currentGroupIndex,
    })

    // ch1 has 6 pages => 3 groups (indices 0, 1, 2)
    expect(paging.pageGroups.value.length).toBe(3)
    expect(paging.showEndCard.value).toBe(false)

    // Since nextChapter exists, lastGroupIndex is the last page group (index 2)
    expect(paging.lastGroupIndex.value).toBe(2)

    currentGroupIndex.value = 2
    expect(paging.atLastGroup.value).toBe(true)
    expect(paging.currentGroupLabel.value).toBe('5–6')
  })

  it('includes End Card when reading the final chapter of a multi-chapter comic', () => {
    const chapters = [
      { id: 'ch1', index: 1, title: '第 1 话', page_count: 6, start: 1 },
      { id: 'ch2', index: 2, title: '第 2 话 (完结)', page_count: 6, start: 7 },
    ]
    const detail = ref<ComicDetail | null>(createMockDetail(12, chapters))
    const scopeId = ref<string | null>('ch2')
    const settings = ref<ReaderSettings>({ ...DEFAULT_SETTINGS, pagesPerView: 2 })
    const currentPage = ref(7)
    const currentGroupIndex = ref(0)

    const paging = useReaderPaging({
      detail,
      scopeId,
      settings,
      currentPage,
      currentGroupIndex,
    })

    expect(paging.pageGroups.value.length).toBe(3)
    expect(paging.showEndCard.value).toBe(true)
    expect(paging.lastGroupIndex.value).toBe(3)

    // Group 3 is End Card
    currentGroupIndex.value = 3
    expect(paging.atLastGroup.value).toBe(true)
    expect(paging.currentGroupLabel.value).toBe('完')
    expect(paging.groupFirstPage(3)).toBe(12)
  })

  it('handles empty comic detail gracefully', () => {
    const detail = ref<ComicDetail | null>(null)
    const scopeId = ref<string | null>(null)
    const settings = ref({ ...DEFAULT_SETTINGS })
    const currentPage = ref(1)
    const currentGroupIndex = ref(0)

    const paging = useReaderPaging({
      detail,
      scopeId,
      settings,
      currentPage,
      currentGroupIndex,
    })

    expect(paging.lastGroupIndex.value).toBe(0)
    expect(paging.currentGroupLabel.value).toBe('—')
    expect(paging.groupFirstPage(0)).toBe(1)
  })
})

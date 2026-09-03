import { describe, expect, it } from 'vite-plus/test'
import { ref } from 'vue'
import { useChapterNavigation } from '@/composables/useChapterNavigation'
import type { ComicDetail } from '@/types'

function makeTestDetail(isMulti = false): ComicDetail {
  return {
    meta: {
      source: 'jm',
      source_id: '518074',
      display_id: '518074',
      title: '测试漫画',
      authors: [],
      works: [],
      actors: [],
      tags: [],
      description: '',
      uploader: null,
      page_count: 100,
      cover_count: 4,
      cover_indices: [],
      pages: Array.from({ length: 100 }, (_, idx) => ({
        index: idx + 1,
        file: `${String(idx + 1).padStart(5, '0')}.webp`,
        ext: '.webp',
        cached: false,
        chapter: isMulti ? (idx < 8 ? 'ch1' : idx < 45 ? 'ch2' : 'ch3') : undefined,
      })),
      chapters: isMulti
        ? [
            { id: 'ch1', index: 1, title: '序章', page_count: 8, start: 1 },
            { id: 'ch2', index: 2, title: '第 1 话', page_count: 37, start: 9 },
            { id: 'ch3', index: 3, title: '第 2 话', page_count: 55, start: 46 },
          ]
        : [],
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

describe('useChapterNavigation', () => {
  it('computes single chapter lastReadLabel with global page number', () => {
    const detail = ref<ComicDetail | null>(makeTestDetail(false))
    const lastRead = ref(15)
    const { lastReadLabel, lastReadChapter } = useChapterNavigation(detail, lastRead)

    expect(lastReadChapter.value).toBeNull()
    expect(lastReadLabel.value).toBe('继续阅读 · 第 15 页')
  })

  it('computes multi-chapter lastReadLabel with chapter-relative page number', () => {
    const detail = ref<ComicDetail | null>(makeTestDetail(true))
    // Chapter 3 starts at 46. Page 47 should be chapter 3, local page 2!
    const lastRead = ref(47)
    const { lastReadLabel, lastReadChapter } = useChapterNavigation(detail, lastRead)

    expect(lastReadChapter.value).not.toBeNull()
    expect(lastReadChapter.value?.id).toBe('ch3')
    expect(lastReadChapter.value?.index).toBe(3)
    expect(lastReadLabel.value).toBe('继续阅读 · 第 3 話 · 第 2 页')
  })

  it('handles first page of chapter 2 correctly', () => {
    const detail = ref<ComicDetail | null>(makeTestDetail(true))
    // Chapter 2 starts at 9. Page 9 should be chapter 2, local page 1!
    const lastRead = ref(9)
    const { lastReadLabel, lastReadChapter } = useChapterNavigation(detail, lastRead)

    expect(lastReadChapter.value?.id).toBe('ch2')
    expect(lastReadLabel.value).toBe('继续阅读 · 第 2 話 · 第 1 页')
  })
})

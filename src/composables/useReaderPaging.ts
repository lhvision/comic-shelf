import { computed, type Ref } from 'vue'
import type { ComicDetail, Chapter } from '@/types'
import type { ReaderSettings } from '@/composables/useReaderSettings'

export interface UseReaderPagingOptions {
  detail: Ref<ComicDetail | null>
  scopeId: Ref<string | null>
  settings: Ref<ReaderSettings>
  currentPage: Ref<number>
  currentGroupIndex: Ref<number>
}

/**
 * 阅读器分页计算、章节作用域映射与边界感知：
 * 负责分屏页码分组（1/2/4页）、全局页码与章内本地页码转换、上一话/下一话导航与边界探测。
 */
export function useReaderPaging(options: UseReaderPagingOptions) {
  const { detail, scopeId, settings, currentPage, currentGroupIndex } = options

  const scopedChapter = computed<Chapter | null>(() => {
    if (!scopeId.value) return null
    const chs = detail.value?.meta.chapters ?? []
    return chs.find((c) => c.id === scopeId.value) ?? null
  })

  const scopedPages = computed<number[]>(() => {
    if (!detail.value) return []
    const c = scopedChapter.value
    if (!c) return Array.from({ length: detail.value.meta.page_count }, (_, i) => i + 1)
    const pages: number[] = []
    for (let p = c.start; p < c.start + c.page_count; p += 1) {
      pages.push(p)
    }
    return pages
  })

  const total = computed(() => scopedPages.value.length)

  function clampToScope(page: number): number {
    const pages = scopedPages.value
    if (pages.length === 0) return 1
    return Math.min(Math.max(page, pages[0]!), pages[pages.length - 1]!)
  }

  const currentChapter = computed<Chapter | null>(() => {
    const chs = detail.value?.meta.chapters ?? []
    if (chs.length <= 1) return null
    const page = currentPage.value
    return chs.find((c) => page >= c.start && page < c.start + c.page_count) ?? null
  })

  const chapterLabel = computed(() => {
    const c = currentChapter.value
    return c ? `第 ${c.index} 話 · ${c.title}` : ''
  })

  const chapters = computed(() => detail.value?.meta.chapters ?? [])

  const currentChapterIndex = computed(() => {
    const cc = currentChapter.value
    return cc ? chapters.value.findIndex((c) => c.id === cc.id) : -1
  })

  const nextChapter = computed<Chapter | null>(() =>
    currentChapterIndex.value >= 0 ? (chapters.value[currentChapterIndex.value + 1] ?? null) : null,
  )

  const prevChapter = computed<Chapter | null>(() =>
    currentChapterIndex.value > 0 ? (chapters.value[currentChapterIndex.value - 1] ?? null) : null,
  )

  const atChapterEnd = computed(() => {
    const c = currentChapter.value
    return c !== null && currentPage.value >= c.start + c.page_count - 1
  })

  const atChapterStart = computed(() => {
    const c = currentChapter.value
    return c !== null && currentPage.value <= c.start
  })

  const showEndCard = computed(() => {
    if (scopedChapter.value === null) return true
    return !nextChapter.value
  })

  const pageGroups = computed<number[][]>(() => {
    const groups: number[][] = []
    const pages = scopedPages.value
    for (let index = 0; index < pages.length; index += settings.value.pagesPerView) {
      groups.push(pages.slice(index, index + settings.value.pagesPerView))
    }
    return groups
  })

  const orderedGroups = computed(() => {
    const withIndex = pageGroups.value.map((pages, index) => ({ pages, index }))
    return settings.value.direction === 'rtl' && settings.value.mode === 'horizontal'
      ? [...withIndex].reverse()
      : withIndex
  })

  const isVertical = computed(() => settings.value.mode !== 'horizontal')
  const rtlHorizontal = computed(
    () => settings.value.mode === 'horizontal' && settings.value.direction === 'rtl',
  )

  const prevSymbol = computed(() => {
    if (settings.value.mode !== 'horizontal') return '↑'
    return settings.value.direction === 'rtl' ? '→' : '←'
  })

  const nextSymbol = computed(() => {
    if (settings.value.mode !== 'horizontal') return '↓'
    return settings.value.direction === 'rtl' ? '←' : '→'
  })

  function toLocalPage(page: number): number {
    const c = scopedChapter.value
    return c ? page - c.start + 1 : page
  }

  const currentGroupLabel = computed(() => {
    const group = pageGroups.value[currentGroupIndex.value]
    if (!group || group.length === 0) return '—'
    if (group.length === 1) return String(toLocalPage(group[0]!))
    return `${toLocalPage(group[0]!)}–${toLocalPage(group[group.length - 1]!)}`
  })

  const lastGroupIndex = computed(() => Math.max(0, pageGroups.value.length - 1))
  const atLastGroup = computed(() => currentGroupIndex.value >= lastGroupIndex.value)

  function groupIndexForPage(page: number): number {
    const groups = pageGroups.value
    for (let index = 0; index < groups.length; index += 1) {
      if (groups[index]!.includes(page)) return index
    }
    return 0
  }

  function groupFirstPage(groupIndex: number): number {
    return pageGroups.value[groupIndex]?.[0] ?? 1
  }

  return {
    scopedChapter,
    scopedPages,
    total,
    clampToScope,
    currentChapter,
    chapterLabel,
    chapters,
    currentChapterIndex,
    nextChapter,
    prevChapter,
    atChapterEnd,
    atChapterStart,
    showEndCard,
    pageGroups,
    orderedGroups,
    isVertical,
    rtlHorizontal,
    prevSymbol,
    nextSymbol,
    toLocalPage,
    currentGroupLabel,
    lastGroupIndex,
    atLastGroup,
    groupIndexForPage,
    groupFirstPage,
  }
}

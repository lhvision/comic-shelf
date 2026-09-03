import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { ComicDetail } from '@/types'

export const CHAPTER_PAGE_STEP = 24

/**
 * 详情页「多章节导航」组合式函数 —— 承载章节切片这块业务编排。
 *
 * 依据 `docs/agents/frontend.md` 的拆分约定：页面视图只做
 * 数据加载/流程编排，领域逻辑收敛到 composable（与 `useReaderSettings` /
 * `useLastRead` 同一模式）。本函数收纳了：
 * - 按当前章节对全局 `meta.pages` 切片（多章节作品仍是全局页码拍平）；
 * - 章节增量渲染（每章 48 页起步）、章节切换时重置计数；
 * - 上次阅读页 → 默认章节 / “继续阅读”带章节文案。
 */
export function useChapterNavigation(detail: Ref<ComicDetail | null>, lastRead: Ref<number>) {
  /** 当前选中章节 id；单章节（无 chapters / length<=1）恒为 null。 */
  const activeChapterId = ref<string | null>(null)
  /** 当前章节内已渲染的页数起点（增量渲染用）。 */
  const visiblePageCount = ref(CHAPTER_PAGE_STEP)

  const chapters = computed(() => detail.value?.meta.chapters ?? [])
  const activeChapter = computed(() => {
    const chs = chapters.value
    if (chs.length <= 1) return null
    return chs.find((c) => c.id === activeChapterId.value) ?? chs[0] ?? null
  })

  /** 当前章节在全局 pages 里的起止（1-based 全局页号）。 */
  const activeChapterStart = computed(() => activeChapter.value?.start ?? 1)
  const activeChapterCount = computed(
    () => activeChapter.value?.page_count ?? detail.value?.meta.page_count ?? 0,
  )

  /** 当前章节展示文案（如「第 2 話 · 标题」）；单章节为空字符串。 */
  const activeChapterLabel = computed(() => {
    const c = activeChapter.value
    return c ? `第 ${c.index} 話 · ${c.title}` : ''
  })

  /** 上次阅读页（限定在全书页数范围内）；单章节作品同样返回全局页。 */
  const progressEl = computed(() =>
    lastRead.value >= 1 && lastRead.value <= (detail.value?.meta.page_count ?? 0)
      ? lastRead.value
      : 0,
  )

  function chapterForPage(page: number): string | null {
    const chs = chapters.value
    if (chs.length <= 1) return null
    return (
      chs.find((c) => page >= c.start && page < c.start + c.page_count)?.id ?? chs[0]?.id ?? null
    )
  }

  const visiblePages = computed(() => {
    if (!detail.value) return []
    const start = activeChapterStart.value - 1
    const end = start + Math.min(activeChapterCount.value, visiblePageCount.value)
    return detail.value.meta.pages.slice(start, end)
  })

  const remainingPages = computed(() => {
    if (!detail.value) return 0
    return Math.max(0, activeChapterCount.value - visiblePageCount.value)
  })

  const showingRange = computed(() => {
    if (!detail.value) return ''
    const end = Math.min(visiblePageCount.value, activeChapterCount.value)
    return `已显示 ${end} / ${activeChapterCount.value} 页`
  })

  const lastReadChapter = computed(() => {
    if (progressEl.value < 1) return null
    const chs = chapters.value
    if (chs.length <= 1) return null
    return (
      chs.find((c) => progressEl.value >= c.start && progressEl.value < c.start + c.page_count) ??
      null
    )
  })

  /** 「继续阅读」按钮文案：多章节时带章节定位与章内相对页码，单章节保持「第 N 页」原文案。 */
  const lastReadLabel = computed(() => {
    if (progressEl.value < 1) return ''
    const c = lastReadChapter.value
    if (c) {
      const localPage = progressEl.value - c.start + 1
      return `继续阅读 · 第 ${c.index} 話 · 第 ${localPage} 页`
    }
    return `继续阅读 · 第 ${progressEl.value} 页`
  })

  // 切换章节：重置本章的增量渲染（第 1 批 48 页）。
  watch(activeChapterId, () => {
    visiblePageCount.value = CHAPTER_PAGE_STEP
  })

  function switchTo(id: string) {
    activeChapterId.value = id
  }

  /** 直接锁到某个章节（子路由进入时用），不受上次阅读位置影响。 */
  function setChapterById(id: string) {
    if (chapters.value.some((c) => c.id === id)) {
      activeChapterId.value = id
      visiblePageCount.value = CHAPTER_PAGE_STEP
    }
  }

  /** 详情刚刚加载完成时，让章节默认跟随上次读到的位置。 */
  function setInitialChapter(page: number) {
    activeChapterId.value = chapterForPage(page)
  }

  function loadMore() {
    visiblePageCount.value = Math.min(
      activeChapterCount.value,
      visiblePageCount.value + CHAPTER_PAGE_STEP,
    )
  }

  return {
    activeChapter,
    activeChapterId,
    activeChapterLabel,
    chapters,
    progressEl,
    visiblePages,
    remainingPages,
    showingRange,
    lastReadLabel,
    lastReadChapter,
    pageStep: CHAPTER_PAGE_STEP,
    switchTo,
    setChapterById,
    setInitialChapter,
    loadMore,
  }
}

export type ChapterNavigation = ReturnType<typeof useChapterNavigation>

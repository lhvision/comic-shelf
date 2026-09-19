/**
 * @file useChapterPageInfo.ts
 * @description 章节详情页专用的章节上下文信息与翻话阅读辅助函数。
 *
 * 领域概念（CONTEXT.md）：
 * 章节子路由详情（Chapter View）
 * 承载当前激活话的起止范围计算、阅读进度换算、相邻话导航及阅读器直达。
 */

import { computed, ref, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import { useHierarchicalNavigation } from '@/composables/useHierarchicalNavigation'
import { useComicDetailWebMCP } from '@/composables/useComicDetailWebMCP'
import { api } from '@/api/client'
import type { Chapter, ComicDetail } from '@/types'

export interface UseChapterPageInfoOptions {
  /** 漫画渠道标识 */
  source: Ref<string>
  /** 漫画车号 ID */
  sourceId: Ref<string>
  /** 当前选中的章节 ID */
  chapterId: Ref<string>
  /** 章节列表 */
  chapters: Ref<Chapter[]>
  /** 漫画完整详情数据引用 */
  detail: Ref<ComicDetail | null>
  /** 上次阅读的全局页码进度（推荐） */
  lastReadPage?: Ref<number>
  /** @deprecated 请优先使用语义明确的 `lastReadPage` */
  progressEl?: Ref<number>
  /** 是否正在缓存 */
  caching?: Ref<boolean>
  /** 正在缓存的章节 ID */
  runningChapterId?: Ref<string | null>
  /** 触发缓存章节函数 */
  cacheChapter?: (chapterId: string) => Promise<void>
  /** 上次阅读页码引用（可选，用于声明式 WebMCP 交互） */
  lastRead?: Ref<number>
}

export function useChapterPageInfo(options: UseChapterPageInfoOptions) {
  const { source, sourceId, chapterId, chapters, detail, caching, runningChapterId, cacheChapter } =
    options
  const lastReadPage = options.lastReadPage ?? options.progressEl ?? ref(0)
  const router = useRouter()
  const { goToChapter: switchActiveChapter, goUpFromChapter } = useHierarchicalNavigation()

  const activeChapter = computed(() => chapters.value.find((c) => c.id === chapterId.value) ?? null)
  const activeIndex = computed(() => chapters.value.findIndex((c) => c.id === chapterId.value))
  const prevChapter = computed(() => chapters.value[activeIndex.value - 1] ?? null)
  const nextChapter = computed(() => chapters.value[activeIndex.value + 1] ?? null)

  if (options.lastRead) {
    useComicDetailWebMCP({
      source,
      sourceId,
      detail,
      chapters,
      lastRead: options.lastRead,
      router,
      cacheChapter,
      activeChapterId: computed(() => activeChapter.value?.id),
      toggleFavorite: async () => {
        if (detail.value) {
          const nextFav = !detail.value.meta.favorite
          detail.value.meta.favorite = nextFav
          await api.setFavorite(source.value, sourceId.value, nextFav)
        }
      },
    })
  }

  const isCurrentChapterCaching = computed(() => {
    if (!caching?.value) return false
    return !runningChapterId?.value || runningChapterId.value === activeChapter.value?.id
  })

  async function cacheCurrentChapter() {
    if (!activeChapter.value || !cacheChapter) return
    await cacheChapter(activeChapter.value.id)
  }

  function goToAlbum() {
    goUpFromChapter(source.value, sourceId.value)
  }

  const activeChapterCached = computed(() => {
    if (!detail.value || !activeChapter.value) return 0
    const ch = activeChapter.value
    let cached = 0
    for (const p of detail.value.meta?.pages ?? []) {
      if (p.chapter === ch.id || (p.index >= ch.start && p.index < ch.start + ch.page_count)) {
        if (p.cached) cached++
      }
    }
    return cached
  })

  const activeChapterTotal = computed(() => activeChapter.value?.page_count ?? 0)

  const chapterRange = computed(() => {
    const c = activeChapter.value
    if (!c) return ''
    const end = c.start + c.page_count - 1
    return `全书第 ${c.start}–${end} 页`
  })

  const isCurrentChapterLastRead = computed(() => {
    if (!activeChapter.value || lastReadPage.value < 1) return false
    const ch = activeChapter.value
    return lastReadPage.value >= ch.start && lastReadPage.value < ch.start + ch.page_count
  })

  const readChapterLabel = computed(() => {
    if (isCurrentChapterLastRead.value && activeChapter.value) {
      const localPage = lastReadPage.value - activeChapter.value.start + 1
      return `继续阅读 · 第 ${localPage} 页`
    }
    return '开始阅读本话'
  })

  function startReadingChapter() {
    if (!activeChapter.value) return
    const targetPage = isCurrentChapterLastRead.value
      ? lastReadPage.value
      : activeChapter.value.start
    void router.push(
      `/comic/${source.value}/${sourceId.value}/read/${targetPage}?chapter=${encodeURIComponent(activeChapter.value.id)}`,
    )
  }

  function goToChapter(id: string) {
    switchActiveChapter(source.value, sourceId.value, id)
  }

  function goPrev() {
    if (prevChapter.value) goToChapter(prevChapter.value.id)
  }

  function goNext() {
    if (!nextChapter.value) return
    goToChapter(nextChapter.value.id)
  }

  // 页面级全局快捷键：[ 上一话，] 下一话（修饰键、弹窗与输入框中静默豁免）
  useEventListener('keydown', (e: KeyboardEvent) => {
    // 忽略长按重复连发，防止高频切话导致路由队列拥堵
    if (e.repeat) return

    // 忽略带修饰键的浏览器/系统组合键（如 macOS Cmd+[ 为浏览器后退）
    if (e.metaKey || e.ctrlKey || e.altKey) return

    // 忽略活动对话框或浮层菜单状态，防止交互中误切底层章节
    if (
      typeof document !== 'undefined' &&
      document.querySelector('dialog[open], [role="dialog"], [role="menu"]')
    ) {
      return
    }

    const target = e.target as HTMLElement | null
    if (
      target &&
      (target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable)
    ) {
      return
    }

    if (e.key === '[' && prevChapter.value) {
      e.preventDefault()
      goPrev()
    } else if (e.key === ']' && nextChapter.value) {
      e.preventDefault()
      goNext()
    }
  })

  return {
    activeChapter,
    activeIndex,
    prevChapter,
    nextChapter,
    activeChapterCached,
    activeChapterTotal,
    chapterRange,
    isCurrentChapterLastRead,
    isCurrentChapterCaching,
    readChapterLabel,
    cacheCurrentChapter,
    goToAlbum,
    startReadingChapter,
    goToChapter,
    goPrev,
    goNext,
  }
}

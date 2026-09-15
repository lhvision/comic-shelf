/**
 * @file useChapterPageInfo.ts
 * @description 章节详情页专用的章节上下文信息与翻话阅读辅助函数。
 *
 * 领域概念（CONTEXT.md）：
 * 章节子路由详情（Chapter View）
 * 承载当前激活话的起止范围计算、阅读进度换算、相邻话导航及阅读器直达。
 */

import { computed, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import { useHierarchicalNavigation } from '@/composables/useHierarchicalNavigation'
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
  /** 上次阅读的全局页码进度 */
  progressEl: Ref<number>
  /** 是否正在缓存 */
  caching?: Ref<boolean>
  /** 正在缓存的章节 ID */
  runningChapterId?: Ref<string | null>
  /** 触发缓存章节函数 */
  cacheChapter?: (chapterId: string) => Promise<void>
}

export function useChapterPageInfo(options: UseChapterPageInfoOptions) {
  const {
    source,
    sourceId,
    chapterId,
    chapters,
    detail,
    progressEl,
    caching,
    runningChapterId,
    cacheChapter,
  } = options
  const router = useRouter()
  const { goToChapter: switchActiveChapter, goUpFromChapter } = useHierarchicalNavigation()

  const activeChapter = computed(() => chapters.value.find((c) => c.id === chapterId.value) ?? null)
  const activeIndex = computed(() => chapters.value.findIndex((c) => c.id === chapterId.value))
  const prevChapter = computed(() => chapters.value[activeIndex.value - 1] ?? null)
  const nextChapter = computed(() => chapters.value[activeIndex.value + 1] ?? null)

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
    if (!activeChapter.value || progressEl.value < 1) return false
    const ch = activeChapter.value
    return progressEl.value >= ch.start && progressEl.value < ch.start + ch.page_count
  })

  const readChapterLabel = computed(() => {
    if (isCurrentChapterLastRead.value && activeChapter.value) {
      const localPage = progressEl.value - activeChapter.value.start + 1
      return `继续阅读 · 第 ${localPage} 页`
    }
    return '开始阅读本话'
  })

  function startReadingChapter() {
    if (!activeChapter.value) return
    const targetPage = isCurrentChapterLastRead.value ? progressEl.value : activeChapter.value.start
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

  // 页面级全局快捷键：[ 上一话，] 下一话（输入框中静默豁免）
  useEventListener('keydown', (e: KeyboardEvent) => {
    const target = e.target as HTMLElement | null
    if (
      target &&
      (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
    ) {
      return
    }
    if (e.key === '[' && prevChapter.value) {
      goPrev()
    } else if (e.key === ']' && nextChapter.value) {
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

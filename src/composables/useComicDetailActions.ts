/**
 * @file useComicDetailActions.ts
 * @description 漫画详情页核心操作与编排（元数据刷新、漫画移除、阅读直达、返回书架与滚动位置恢复）。
 *
 * 领域概念（CONTEXT.md）：
 * 漫画详情页（Comic Detail View）
 * 承载单本漫画的作品概览、章节目录切片、画页重订与元数据维护。
 */

import { nextTick, ref, type Ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { useLibraryStore } from '@/stores/library'
import { useToast } from '@/composables/useToast'
import { useCoverTransition } from '@/composables/useCoverTransition'
import { useHierarchicalNavigation } from '@/composables/useHierarchicalNavigation'
import {
  getDetailScrollPosition,
  setDetailScrollPosition,
} from '@/composables/useChapterNavigation'
import type { Chapter, ComicDetail } from '@/types'

export interface UseComicDetailActionsOptions {
  /** 渠道来源标识 */
  source: Ref<string>
  /** 漫画车号 ID */
  sourceId: Ref<string>
  /** 漫画详情数据引用 */
  detail: Ref<ComicDetail | null>
  /** 章节列表 */
  chapters: Ref<Chapter[]>
  /** 阅读进度全局页码 */
  progressEl: Ref<number>
  /** 全局页码到所属章节映射函数 */
  chapterForPage: (page: number) => string | null | undefined
  /** 重新加载详情回调 */
  load: () => Promise<void>
}

export function useComicDetailActions(options: UseComicDetailActionsOptions) {
  const { source, sourceId, detail, chapters, progressEl, chapterForPage, load } = options
  const router = useRouter()
  const store = useLibraryStore()
  const { toast } = useToast()
  const { setActiveCover } = useCoverTransition()
  const { goUpFromDetail } = useHierarchicalNavigation()

  // 弹窗状态
  const editOpen = ref(false)
  const appendOpen = ref(false)
  const replaceOpen = ref(false)

  function restoreScrollPosition() {
    const key = `${source.value}/${sourceId.value}`
    const saved = getDetailScrollPosition(key)
    if (saved !== undefined && saved > 0) {
      void nextTick(() => {
        window.scrollTo({ top: saved, behavior: 'instant' })
      })
    }
  }

  onBeforeRouteLeave((to) => {
    if (to.name === 'comic-chapter' || to.name === 'reader') {
      setDetailScrollPosition(`${source.value}/${sourceId.value}`, window.scrollY)
    }
  })

  async function removeComic() {
    if (!detail.value) return
    try {
      await store.remove(source.value, sourceId.value)
      toast('已从纸间移除')
      void router.replace('/')
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    }
  }

  async function refreshMetadata() {
    try {
      const prevPageCount = detail.value?.meta.page_count ?? 0
      const prevChapterCount = chapters.value?.length ?? 0
      const result = await store.importComic({
        id: sourceId.value,
        source: source.value,
        prefetch_covers: 4,
        refresh: true,
      })
      await load()
      const nextPageCount = result.meta.page_count ?? 0
      const nextChapterCount = result.meta.chapters?.length ?? 0
      if (nextPageCount > prevPageCount || nextChapterCount > prevChapterCount) {
        const newChaps = nextChapterCount - prevChapterCount
        const newPages = nextPageCount - prevPageCount
        if (newChaps > 0) {
          toast(`已增量更新：新增 ${newChaps} 话（共 ${newPages} 页），旧缓存已保留`)
        } else {
          toast(`已增量更新：新增 ${newPages} 页，旧缓存已保留`)
        }
      } else {
        toast('资料已刷新，当前已是最新版本')
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    }
  }

  function goBack() {
    setActiveCover(source.value, sourceId.value)
    goUpFromDetail(source.value, sourceId.value)
  }

  function startReading(page = progressEl.value || 1) {
    const chapterId = chapterForPage(page)
    const path = chapterId
      ? `/comic/${source.value}/${sourceId.value}/read/${page}?chapter=${encodeURIComponent(chapterId)}`
      : `/comic/${source.value}/${sourceId.value}/read/${page}`
    void router.push(path)
  }

  return {
    editOpen,
    appendOpen,
    replaceOpen,
    restoreScrollPosition,
    removeComic,
    refreshMetadata,
    goBack,
    startReading,
  }
}

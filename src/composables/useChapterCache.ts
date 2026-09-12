/**
 * @file useChapterCache.ts
 * @description 漫画全书与分话后台缓存轮询与进度状态编排 Composable
 *
 * 核心职责：
 * 1. 任务驱动轮询：基于 useIntervalFn（1000ms）在后台任务运行期间自适应轮询进度；
 * 2. 页码状态就地标记：根据服务端返回的 job.prefetched 与 chapterProgress，精准就地更新 meta.pages 状态；
 * 3. 任务生命周期对齐：在缓存启动时通过 beginTask 注册，完成或异常时通过 endTask 注销，配合系统事件流自适应起停；
 * 4. 跨视图逻辑统一：收敛 ComicDetailView 与 ChapterView 中重复的进度轮询与状态机，降低视图胶水代码量。
 */

import { ref, type Ref } from 'vue'
import { useIntervalFn, tryOnScopeDispose } from '@vueuse/core'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useLibraryStore } from '@/stores/library'
import { useSystemEvents, getTaskId } from '@/composables/useSystemEvents'
import type { CacheJob, Chapter, ComicDetail } from '@/types'

export interface UseChapterCacheOptions {
  /** 漫画来源标识（如 'jm', 'local'） */
  source: Ref<string>
  /** 漫画来源内部 ID */
  sourceId: Ref<string>
  /** 当前漫画详情引用 */
  detail: Ref<ComicDetail | null>
  /** 章节列表引用 */
  chapters: Ref<Chapter[]>
  /** 当前激活的章节 ID（仅章节子路由视图使用） */
  activeChapterId?: Ref<string | undefined | null>
  /** 缓存任务完成时静默对齐数据的回调函数 */
  onRefresh?: () => Promise<void> | void
}

export function useChapterCache(options: UseChapterCacheOptions) {
  const { source, sourceId, detail, chapters, activeChapterId, onRefresh } = options
  const { toast } = useToast()
  const store = useLibraryStore()
  const { beginTask, endTask } = useSystemEvents()

  const caching = ref(false)
  const runningChapterId = ref<string | null>(null)

  let isPollingProgress = false

  /**
   * 精准就地标记已完成的页码状态
   */
  function markPagesCached(
    job: { running: boolean; chapter_id?: string | null; prefetched: number },
    isComplete = false,
    targetChapterId?: string | null,
  ): void {
    if (!detail.value?.meta?.pages) return
    const pages = detail.value.meta.pages

    if (job.chapter_id) {
      const ch = chapters.value.find((c) => c.id === job.chapter_id)
      if (ch) {
        const maxPage = ch.start + job.prefetched - 1
        for (const p of pages) {
          if (p.chapter === ch.id && (!job.running || p.index <= maxPage)) {
            p.cached = true
          }
        }
      }
    } else if (isComplete) {
      for (const p of pages) {
        p.cached = true
      }
    } else if (job.running && !job.chapter_id) {
      for (const p of pages) {
        if (p.index <= job.prefetched) {
          p.cached = true
        }
      }
    }

    if (targetChapterId && isComplete) {
      for (const p of pages) {
        if (p.chapter === targetChapterId) {
          p.cached = true
        }
      }
    }
  }

  const { pause: pauseProgressPolling, resume: resumeProgressPolling } = useIntervalFn(
    async () => {
      if (isPollingProgress) return
      isPollingProgress = true
      try {
        const currentChapterId = activeChapterId?.value
        const [progress, job] = await Promise.all([
          currentChapterId
            ? api.chapterCacheProgress(source.value, sourceId.value, currentChapterId)
            : api.cacheProgress(source.value, sourceId.value),
          api.cacheJob(source.value, sourceId.value),
        ])

        caching.value = job.running
        runningChapterId.value = job.chapter_id ?? null

        if (detail.value) {
          if (!currentChapterId) {
            detail.value.cached_pages = Math.max(detail.value.cached_pages, progress.cached)
            detail.value.cache_complete = progress.complete
          }
          markPagesCached(job, progress.complete, currentChapterId)
        }

        const isFinished = currentChapterId
          ? !job.running || (job.chapter_id === currentChapterId && progress.complete)
          : !job.running || progress.complete

        const wasCaching = caching.value
        if (isFinished) {
          caching.value = false
          runningChapterId.value = null
          endTask(getTaskId.cache(source.value, sourceId.value))
          if (job.chapter_id) {
            endTask(getTaskId.chapter(source.value, sourceId.value, job.chapter_id))
          }
          if (currentChapterId) {
            endTask(getTaskId.chapter(source.value, sourceId.value, currentChapterId))
          }
          pauseProgressPolling()
          if (wasCaching && !progress.complete && job.warnings && job.warnings.length > 0) {
            toast(`有 ${job.warnings.length} 页下载中断，点击“缓存全部”可继续重试`, 'info')
          }
          if (onRefresh) {
            void onRefresh()
          }
        }
      } catch {
        /* transient network error; let retry or main caller handle */
      } finally {
        isPollingProgress = false
      }
    },
    1000,
    { immediate: false },
  )

  function startProgressPolling(): void {
    pauseProgressPolling()
    resumeProgressPolling()
  }

  /**
   * 同步服务端返回的最新 cacheJob 状态并自适应开启/暂停轮询
   */
  function syncJobState(job: CacheJob): void {
    caching.value = job.running
    runningChapterId.value = job.chapter_id ?? null
    if (job.running) {
      beginTask(
        job.chapter_id
          ? getTaskId.chapter(source.value, sourceId.value, job.chapter_id)
          : getTaskId.cache(source.value, sourceId.value),
      )
      startProgressPolling()
    } else {
      pauseProgressPolling()
    }
  }

  /**
   * 触发全本缓存后台任务
   */
  async function cacheAll(): Promise<void> {
    if (!detail.value || caching.value) return
    caching.value = true
    runningChapterId.value = null
    const taskId = getTaskId.cache(source.value, sourceId.value)
    beginTask(taskId)
    startProgressPolling()
    try {
      const progress = await api.cacheAll(source.value, sourceId.value)
      detail.value.cached_pages = progress.cached
      detail.value.cache_complete = progress.complete
      if (progress.complete && detail.value.meta?.pages) {
        for (const p of detail.value.meta.pages) {
          p.cached = true
        }
      }
      await store.load()
      toast(progress.complete ? '已全部缓存到本地' : '后台缓存进行中，进度会自动更新', 'info')
      if (progress.complete) {
        endTask(taskId)
        pauseProgressPolling()
        caching.value = false
        if (onRefresh) {
          void onRefresh()
        }
      } else {
        resumeProgressPolling()
      }
    } catch (e) {
      endTask(taskId)
      pauseProgressPolling()
      caching.value = false
      toast(e instanceof Error ? e.message : String(e), 'error')
    }
  }

  /**
   * 触发单章节缓存后台任务
   */
  async function cacheChapter(chapterId: string): Promise<void> {
    if (!detail.value || caching.value) return
    caching.value = true
    runningChapterId.value = chapterId
    const taskId = getTaskId.chapter(source.value, sourceId.value, chapterId)
    beginTask(taskId)
    startProgressPolling()
    try {
      const progress = await api.cacheChapter(source.value, sourceId.value, chapterId)
      const ch = chapters.value.find((c) => c.id === chapterId)
      if (ch && detail.value.meta?.pages && progress.complete) {
        for (const p of detail.value.meta.pages) {
          if (p.chapter === chapterId) {
            p.cached = true
          }
        }
      }
      const label = ch?.title || (ch?.index !== undefined ? `第 ${ch.index} 話` : '章节')
      toast(
        progress.complete ? `「${label}」已缓存完毕` : `已开始缓存「${label}」，进度会自动更新`,
        'info',
      )
      if (progress.complete) {
        endTask(taskId)
        pauseProgressPolling()
        caching.value = false
        runningChapterId.value = null
        if (onRefresh) {
          void onRefresh()
        }
      }
    } catch (e) {
      endTask(taskId)
      pauseProgressPolling()
      caching.value = false
      runningChapterId.value = null
      toast(e instanceof Error ? e.message : String(e), 'error')
    }
  }

  /**
   * 单页缓存状态的原地标记回调，供 PageList / VirtualGrid @page-cached 统一消费
   */
  function onPageCached(pageIndex: number): void {
    if (!detail.value?.meta?.pages) return
    const page = detail.value.meta.pages.find((p) => p.index === pageIndex)
    if (page && !page.cached) {
      page.cached = true
      const currentCachedCount = detail.value.meta.pages.filter((p) => p.cached).length
      detail.value.cached_pages = Math.max(detail.value.cached_pages, currentCachedCount)
      detail.value.cache_complete = detail.value.cached_pages >= detail.value.meta.page_count
    }
  }

  tryOnScopeDispose(() => {
    pauseProgressPolling()
  })

  return {
    caching,
    runningChapterId,
    startProgressPolling,
    pauseProgressPolling,
    resumeProgressPolling,
    syncJobState,
    cacheAll,
    cacheChapter,
    markPagesCached,
    onPageCached,
  }
}

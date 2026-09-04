import { computed, ref } from 'vue'
import { tryOnScopeDispose, useIntervalFn } from '@vueuse/core'
import { defineStore } from 'pinia'
import { api, onAuthSuccess } from '@/api/client'
import type { ComicDetail, ImportRequest, LibrarySummary } from '@/types'

export interface LiveCacheState {
  running: boolean
  cached: number
  total: number
}

export const liveCacheKey = (source: string, sourceId: string) => `${source}/${sourceId}`

/**
 * 基于书架概要数据构造初始 ComicDetail 占位结构。
 * 用于从书架进入详情页时立即呈现 Hero 头部（标题、封面轮播、元数据与操作栏），
 * 让 View Transition 能精准捕获并连贯执行 Shared Cover Morph，杜绝白屏/灰骨架屏闪烁。
 */
export function createPlaceholderDetail(s: LibrarySummary): ComicDetail {
  return {
    meta: {
      source: s.source,
      source_id: s.source_id,
      display_id: s.display_id,
      title: s.title,
      authors: s.authors,
      works: s.works,
      actors: s.actors,
      tags: s.tags,
      description: '',
      uploader: '',
      page_count: s.page_count,
      cover_count: s.cover_count,
      cover_indices: [],
      pages: Array.from({ length: s.page_count }, (_, idx) => ({
        index: idx + 1,
        file: `${String(idx + 1).padStart(5, '0')}.webp`,
        ext: '.webp',
        cached: idx < s.cached_pages,
        chapter: s.chapter_titles?.length ? '1' : undefined,
      })),
      chapters: (s.chapter_titles ?? []).map((title, idx) => ({
        id: String(idx + 1),
        index: idx + 1,
        title,
        page_count: 0,
        start: 1,
      })),
      views: s.views,
      likes: s.likes,
      comment_count: 0,
      favorite: s.favorite,
      hidden_from_guest: s.hidden_from_guest,
      source_url: '',
      published_at: s.published_at,
      updated_at: s.updated_at,
      imported_at: s.imported_at,
      last_checked_at: s.imported_at,
      raw: {},
    },
    cached_pages: s.cached_pages,
    cache_complete: s.cached_pages >= s.page_count,
    cover_paths: s.cover_paths,
  }
}

export const useLibraryStore = defineStore('library', () => {
  const items = ref<LibrarySummary[]>([])
  const loading = ref(false)
  const importing = ref(false)
  const error = ref('')
  const importMessage = ref('')
  /** Live cache progress for comics with a running background prefetch job. */
  const liveCache = ref<Record<string, LiveCacheState>>({})
  /** In-memory cache for full ComicDetail to prevent re-fetching/re-parsing huge JSONs on view navigation */
  const detailCache = ref<Record<string, ComicDetail>>({})

  const displayItems = computed(() => items.value)

  const activeCachingCount = computed(() => Object.keys(liveCache.value).length)
  let libraryAbortController: AbortController | null = null

  async function loadItems(silent = false) {
    if (libraryAbortController) {
      libraryAbortController.abort()
    }
    const controller = new AbortController()
    libraryAbortController = controller

    // SWR：仅在内存中尚无数据且非静默模式时才置 loading = true 展示骨架屏；
    // 若已有数据，则保持现有卡片平滑展示，后台静默对齐最新状态，杜绝切页闪烁。
    if (!silent && items.value.length === 0) {
      loading.value = true
    }

    try {
      const data = await api.library({ signal: controller.signal })
      if (libraryAbortController === controller) {
        items.value = data
        error.value = ''
      }
    } catch (e) {
      if (controller.signal.aborted) return
      const msg = e instanceof Error ? e.message : String(e)
      // When unauthenticated, the auth modal guides the user; don't trigger loud error toast
      if (!msg.includes('401') && !msg.includes('未授权')) {
        error.value = msg
      }
    } finally {
      if (libraryAbortController === controller) {
        loading.value = false
        libraryAbortController = null
      }
    }
  }

  // Reload data automatically as soon as auth succeeds
  onAuthSuccess(() => {
    error.value = ''
    void load()
  })

  let isRefreshingLiveCache = false
  let refreshAbortController: AbortController | null = null

  async function refreshLiveCache() {
    if (isRefreshingLiveCache) return
    isRefreshingLiveCache = true
    refreshAbortController = new AbortController()
    const signal = refreshAbortController.signal
    const previousKeys = new Set(Object.keys(liveCache.value))
    try {
      const jobs = await api.cacheJobs({ signal })
      const running = jobs.filter((job) => job.running)
      const next: Record<string, LiveCacheState> = {}
      await Promise.all(
        running.map(async (job) => {
          const key = liveCacheKey(job.source, job.source_id)
          const prev = liveCache.value[key]
          try {
            const progress = await api.cacheProgress(job.source, job.source_id, { signal })
            const cached = Math.max(progress.cached, prev?.cached ?? 0)
            next[key] = { running: true, cached, total: progress.total }
          } catch {
            const cached = Math.max(job.prefetched, prev?.cached ?? 0)
            next[key] = {
              running: true,
              cached,
              total: Math.max(job.total, job.prefetched, prev?.total ?? 0),
            }
          }
        }),
      )

      // A finished job must not leave the card showing stale static counts;
      // resync the shelf snapshot from disk BEFORE releasing the live cache lock.
      const finishedSomething =
        previousKeys.size > 0 && Object.keys(next).length < previousKeys.size

      if (finishedSomething) {
        await loadItems(true)
        if (importMessage.value.includes('后台缓存')) {
          clearImportMessage()
        }
      }

      liveCache.value = next

      if (running.length === 0) poll.pause()
    } catch {
      /* transient; keep whatever we had and pause polling to avoid hammering failing backend/WAF */
      poll.pause()
    } finally {
      isRefreshingLiveCache = false
      refreshAbortController = null
    }
  }

  let importMessageTimer: ReturnType<typeof setTimeout> | null = null

  function setImportMessage(msg: string, autoDismissMs = 6000) {
    if (importMessageTimer) clearTimeout(importMessageTimer)
    importMessage.value = msg
    if (msg && autoDismissMs > 0) {
      importMessageTimer = setTimeout(() => {
        if (importMessage.value === msg) {
          importMessage.value = ''
        }
      }, autoDismissMs)
    }
  }

  function clearImportMessage() {
    if (importMessageTimer) clearTimeout(importMessageTimer)
    importMessage.value = ''
  }

  tryOnScopeDispose(() => {
    if (importMessageTimer) clearTimeout(importMessageTimer)
    stopPolling()
  })

  const poll = useIntervalFn(refreshLiveCache, 2000, { immediate: false })

  function startPollingIfActive() {
    poll.resume()
    void refreshLiveCache()
  }

  function stopPolling() {
    poll.pause()
    if (refreshAbortController) {
      refreshAbortController.abort()
      refreshAbortController = null
    }
  }

  function markCaching(source: string, sourceId: string) {
    const key = liveCacheKey(source, sourceId)
    const existing = byId(source, sourceId)
    const initialCached = existing?.cached_pages ?? 0
    const initialTotal = existing?.page_count ?? 0
    if (!liveCache.value[key]) {
      liveCache.value[key] = { running: true, cached: initialCached, total: initialTotal }
    }
    poll.resume()
  }

  function liveFor(item: LibrarySummary) {
    return liveCache.value[liveCacheKey(item.source, item.source_id)]
  }

  async function load(silent = false) {
    await loadItems(silent)
    // A page reload shouldn't lose the live "缓存中" state on the shelf.
    await refreshLiveCache()
  }

  async function importComic(payload: ImportRequest) {
    importing.value = true
    clearImportMessage()
    error.value = ''
    try {
      const result = await api.importComic(payload)
      const msg = result.from_cache
        ? `${result.meta.display_id} 已在本机，没有访问远端`
        : result.background
          ? `${result.meta.display_id} 已收录，页面正在后台缓存`
          : `${result.meta.display_id} 已收录，本次预缓存 ${result.prefetched} 页`
      const fullMsg =
        result.warnings.length > 0 ? `${msg}（${result.warnings.length} 条提醒）` : msg
      setImportMessage(fullMsg, 6000)

      if (result.background) {
        markCaching(result.meta.source, result.meta.source_id)
      }
      await load()
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      importing.value = false
    }
  }

  async function remove(source: string, sourceId: string) {
    await api.deleteComic(source, sourceId)
    removeDetail(source, sourceId)
    await load()
  }

  function byId(source: string, sourceId: string) {
    return items.value.find((item) => item.source === source && item.source_id === sourceId)
  }

  /**
   * 本地乐观更新「喜欢」标记：书架卡片的 FavoriteButton 已经完成了 API 调用，
   * 这里只原地改内存里的那一项，不整表刷新，避免列表全部重绘闪屏。
   */
  function setFavoriteLocal(source: string, sourceId: string, favorite: boolean) {
    const item = byId(source, sourceId)
    if (item) item.favorite = favorite
  }

  /**
   * 本地乐观更新「阅读进度」标记：读者在阅读器翻页或读完时，
   * 原地改内存里的 last_page，不整表刷新，保证书架排序与状态印章即时响应。
   */
  function setReadingProgressLocal(source: string, sourceId: string, page: number) {
    const item = byId(source, sourceId)
    if (item) item.last_page = page
  }

  const MAX_DETAIL_CACHE = 20

  function getDetail(source: string, sourceId: string): ComicDetail | undefined {
    return detailCache.value[`${source}/${sourceId}`]
  }

  function setDetail(detail: ComicDetail) {
    const key = `${detail.meta.source}/${detail.meta.source_id}`
    delete detailCache.value[key]
    detailCache.value[key] = detail
    const keys = Object.keys(detailCache.value)
    if (keys.length > MAX_DETAIL_CACHE) {
      const oldest = keys[0]
      if (oldest) delete detailCache.value[oldest]
    }
  }

  function removeDetail(source: string, sourceId: string) {
    delete detailCache.value[`${source}/${sourceId}`]
  }

  return {
    items,
    displayItems,
    loading,
    importing,
    error,
    importMessage,
    liveCache,
    activeCachingCount,
    load,
    importComic,
    remove,
    byId,
    getDetail,
    setDetail,
    removeDetail,
    setFavoriteLocal,
    setReadingProgressLocal,
    liveFor,
    startPollingIfActive,
    stopPolling,
    setImportMessage,
    clearImportMessage,
  }
})

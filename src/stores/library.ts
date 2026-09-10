import { computed, ref } from 'vue'
import { tryOnScopeDispose, useIntervalFn } from '@vueuse/core'
import { defineStore } from 'pinia'
import { api, onAuthSuccess } from '@/api/client'
import { getTaskId, useSystemEvents } from '@/composables/useSystemEvents'
import { useAuth } from '@/composables/useAuth'
import {
  getShelfSnapshot,
  saveShelfSnapshot,
  getComicDetail as getOfflineComicDetail,
  saveComicDetail as saveOfflineComicDetail,
} from '@/utils/offlineDb'
import type {
  ComicDetail,
  ImportRequest,
  LibraryFacetsResponse,
  LibraryQueryParams,
  LibrarySummary,
} from '@/types'

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
  const { beginTask, endTask, broadcastLocalChange } = useSystemEvents()
  const { userId } = useAuth()

  const items = ref<LibrarySummary[]>([])
  const loading = ref(false)
  const importing = ref(false)
  const error = ref('')
  const importMessage = ref('')
  const isOffline = ref(false)
  const hydratedFromOffline = ref(false)

  /** Live cache progress for comics with a running background prefetch job. */
  const liveCache = ref<Record<string, LiveCacheState>>({})
  /** In-memory cache for full ComicDetail to prevent re-fetching/re-parsing huge JSONs on view navigation */
  const detailCache = ref<Record<string, ComicDetail>>({})

  const facets = ref<LibraryFacetsResponse | null>(null)
  const page = ref(1)
  const pageSize = ref(24)
  const total = ref(0)
  const hasMore = ref(false)
  const loadingMore = ref(false)
  const currentParams = ref<LibraryQueryParams>({})

  const displayItems = computed(() => items.value)
  const activeCachingCount = computed(() => Object.keys(liveCache.value).length)
  let libraryAbortController: AbortController | null = null

  /**
   * 从端侧 IndexedDB 离线镜像中秒级还原书架数据
   */
  async function hydrateFromOfflineSnapshot(targetUserId?: string): Promise<boolean> {
    try {
      const uid = targetUserId ?? userId.value ?? ''
      const snapshot = await getShelfSnapshot(uid)
      if (snapshot && Array.isArray(snapshot.items) && snapshot.items.length > 0) {
        if (items.value.length === 0) {
          items.value = snapshot.items
          facets.value = snapshot.facets ?? null
          total.value = snapshot.items.length
        }
        hydratedFromOffline.value = true
        return true
      }
    } catch {
      // ignore IndexedDB error
    }
    return false
  }

  async function loadFacets(source?: string) {
    try {
      facets.value = await api.libraryFacets(source)
    } catch {
      // ignore
    }
  }

  async function loadItems(
    silent = false,
    append = false,
    params?: LibraryQueryParams,
    targetUserId?: string,
  ) {
    if (!append && libraryAbortController) {
      libraryAbortController.abort()
    }
    const controller = new AbortController()
    if (!append) {
      libraryAbortController = controller
    }

    if (params) {
      const { page: _p, offset: _o, page_size: _ps, ...filters } = params
      currentParams.value = { ...currentParams.value, ...filters }
    }

    const targetPage = append ? page.value + 1 : (params?.page ?? 1)
    const queryParams: LibraryQueryParams = {
      ...currentParams.value,
      page: targetPage,
      page_size: params?.page_size ?? pageSize.value,
      offset: params?.offset ?? (append ? items.value.length : undefined),
    }

    const uid = targetUserId ?? userId.value ?? ''

    if (append) {
      loadingMore.value = true
    } else if (!silent && items.value.length === 0) {
      // 若内存尚无数据，先尝试从端侧快照 0ms 呈现
      void hydrateFromOfflineSnapshot(uid)
      if (items.value.length === 0) {
        loading.value = true
      }
    }

    try {
      const data = await api.library(queryParams, { signal: controller.signal })
      if (!append && libraryAbortController !== controller) return

      if (append) {
        const existingKeys = new Set(items.value.map((i) => `${i.source}:${i.source_id}`))
        const incoming = Array.isArray(data?.items) ? data.items : []
        const uniqueIncoming = incoming.filter(
          (i) => !existingKeys.has(`${i.source}:${i.source_id}`),
        )
        items.value = [...items.value, ...uniqueIncoming]
      } else {
        items.value = Array.isArray(data?.items) ? data.items : []
      }
      page.value = data.page
      total.value = data.total
      hasMore.value = data.has_more
      error.value = ''
      isOffline.value = false

      // 默认全量首页刷新时（非临时关键词搜索/标签细分），异步更新端侧 IndexedDB 快照镜像
      const isFilteredQuery = Boolean(
        params?.search ||
        params?.tag ||
        (params?.status && params.status !== 'all') ||
        params?.favorite ||
        params?.ids,
      )
      if (!append && !isFilteredQuery && Array.isArray(items.value) && items.value.length > 0) {
        void saveShelfSnapshot(uid, {
          items: items.value,
          facets: facets.value,
        })
      }
    } catch (e) {
      if (controller.signal.aborted) return
      const msg = e instanceof Error ? e.message : String(e)

      // 探测是否属于断网或离线故障
      const isNetworkError =
        msg.includes('Failed to fetch') ||
        msg.includes('NetworkError') ||
        msg.includes('Load failed') ||
        msg.includes('请求超时') ||
        (typeof navigator !== 'undefined' && !navigator.onLine)

      if (isNetworkError) {
        isOffline.value = true
        if (items.value.length === 0) {
          await hydrateFromOfflineSnapshot(uid)
        }
      }

      // 仅在非未授权且当前界面完全空屏时暴露错误，有离线缓存时保持从容
      if (!msg.includes('401') && !msg.includes('未授权') && items.value.length === 0) {
        error.value = msg
      }
    } finally {
      if (append) {
        loadingMore.value = false
      } else if (libraryAbortController === controller) {
        loading.value = false
        libraryAbortController = null
      }
    }
  }

  async function loadMore() {
    if (loadingMore.value || !hasMore.value) return
    await loadItems(true, true)
  }

  async function loadAll(maxCap = 240) {
    if (loadingMore.value || !hasMore.value) return
    while (hasMore.value && items.value.length < maxCap) {
      const remaining = Math.min(120, maxCap - items.value.length)
      await loadItems(true, true, {
        offset: items.value.length,
        page_size: remaining,
      })
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
    if (isRefreshingLiveCache || isOffline.value) return
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
        await loadFacets(currentParams.value.source)
        if (importMessage.value.includes('后台缓存')) {
          clearImportMessage()
        }
      }

      liveCache.value = next

      if (running.length > 0) {
        beginTask(getTaskId.liveCache())
      } else {
        endTask(getTaskId.liveCache())
        poll.pause()
      }
    } catch {
      /* transient; keep whatever we had and pause polling to avoid hammering failing backend/WAF */
      endTask(getTaskId.liveCache())
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
    if (isOffline.value) return
    poll.resume()
    void refreshLiveCache()
  }

  function stopPolling() {
    poll.pause()
    endTask(getTaskId.liveCache())
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

  async function load(silent = false, params?: LibraryQueryParams, userId?: string) {
    await Promise.all([loadItems(silent, false, params, userId), loadFacets(params?.source)])
    if (!isOffline.value) {
      await refreshLiveCache()
    }
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
        beginTask(getTaskId.import(result.meta.source, result.meta.source_id))
      }
      broadcastLocalChange({
        action: 'import',
        source: result.meta.source,
        source_id: result.meta.source_id,
        timestamp: Date.now(),
      })
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
    broadcastLocalChange({
      action: 'delete',
      source,
      source_id: sourceId,
      timestamp: Date.now(),
    })
  }

  function byId(source: string, sourceId: string) {
    return items.value.find((item) => item.source === source && item.source_id === sourceId)
  }

  /**
   * 本地乐观更新「喜欢」标记：书架卡片的 FavoriteButton 已经完成了 API 调用或离线入队，
   * 这里只原地改内存里的那一项，不整表刷新，避免列表全部重绘闪屏。
   */
  function setFavoriteLocal(source: string, sourceId: string, favorite: boolean, userId?: string) {
    const item = byId(source, sourceId)
    if (item) {
      item.favorite = favorite
      void saveShelfSnapshot(userId ?? '', { items: items.value, facets: facets.value })
    }
  }

  /**
   * 本地乐观更新「阅读进度」标记：读者在阅读器翻页或读完时，
   * 原地改内存里的 last_page，不整表刷新，保证书架排序与状态印章即时响应。
   */
  function setReadingProgressLocal(
    source: string,
    sourceId: string,
    page: number,
    userId?: string,
  ) {
    const item = byId(source, sourceId)
    if (item) {
      item.last_page = page
      void saveShelfSnapshot(userId ?? '', { items: items.value, facets: facets.value })
    }
  }

  const MAX_DETAIL_CACHE = 20

  function getDetail(source: string, sourceId: string): ComicDetail | undefined {
    return detailCache.value[`${source}/${sourceId}`]
  }

  async function getOrFetchOfflineDetail(
    source: string,
    sourceId: string,
    userId?: string,
  ): Promise<ComicDetail | null> {
    const memory = getDetail(source, sourceId)
    if (memory) return memory

    const offlineRecord = await getOfflineComicDetail(userId ?? '', source, sourceId)
    if (offlineRecord) {
      setDetail(offlineRecord)
      return offlineRecord
    }
    return null
  }

  function setDetail(detail: ComicDetail, userId?: string) {
    const key = `${detail.meta.source}/${detail.meta.source_id}`
    delete detailCache.value[key]
    detailCache.value[key] = detail
    const keys = Object.keys(detailCache.value)
    if (keys.length > MAX_DETAIL_CACHE) {
      const oldest = keys[0]
      if (oldest) delete detailCache.value[oldest]
    }

    // 异步同步到端侧 IndexedDB 镜像
    void saveOfflineComicDetail(userId ?? '', detail)
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
    isOffline,
    hydratedFromOffline,
    liveCache,
    activeCachingCount,
    facets,
    page,
    pageSize,
    total,
    hasMore,
    loadingMore,
    currentParams,
    hydrateFromOfflineSnapshot,
    load,
    loadItems,
    loadFacets,
    loadMore,
    loadAll,
    importComic,
    remove,
    byId,
    getDetail,
    getOrFetchOfflineDetail,
    setDetail,
    removeDetail,
    markCaching,
    setFavoriteLocal,
    setReadingProgressLocal,
    liveFor,
    startPollingIfActive,
    stopPolling,
    setImportMessage,
    clearImportMessage,
  }
})

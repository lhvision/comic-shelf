import { computed, ref } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { ImportRequest, LibrarySummary } from '@/types'

export interface LiveCacheState {
  running: boolean
  cached: number
  total: number
}

export const liveCacheKey = (source: string, sourceId: string) => `${source}/${sourceId}`

export const useLibraryStore = defineStore('library', () => {
  const items = ref<LibrarySummary[]>([])
  const loading = ref(false)
  const importing = ref(false)
  const error = ref('')
  const importMessage = ref('')
  /** Live cache progress for comics with a running background prefetch job. */
  const liveCache = ref<Record<string, LiveCacheState>>({})

  const displayItems = computed(() => items.value)

  const activeCachingCount = computed(() => Object.keys(liveCache.value).length)

  async function loadItems() {
    loading.value = true
    error.value = ''
    try {
      items.value = await api.library()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function refreshLiveCache() {
    const previousKeys = new Set(Object.keys(liveCache.value))
    try {
      const jobs = await api.cacheJobs()
      const running = jobs.filter((job) => job.running)
      const next: Record<string, LiveCacheState> = {}
      await Promise.all(
        running.map(async (job) => {
          const key = liveCacheKey(job.source, job.source_id)
          try {
            const progress = await api.cacheProgress(job.source, job.source_id)
            next[key] = { running: true, cached: progress.cached, total: progress.total }
          } catch {
            next[key] = {
              running: true,
              cached: job.prefetched,
              total: Math.max(job.total, job.prefetched),
            }
          }
        }),
      )

      // A finished job must not leave the card showing stale static counts;
      // resync the shelf snapshot from disk exactly when a job completes.
      const finishedSomething =
        previousKeys.size > 0 && Object.keys(next).length < previousKeys.size
      liveCache.value = next

      if (finishedSomething) {
        await loadItems()
      }
      if (running.length === 0) poll.pause()
    } catch {
      /* transient; keep whatever we had */
    }
  }

  const poll = useIntervalFn(refreshLiveCache, 2000, { immediate: false })

  function startPollingIfActive() {
    poll.resume()
    void refreshLiveCache()
  }

  function stopPolling() {
    poll.pause()
  }

  function markCaching(source: string, sourceId: string) {
    const key = liveCacheKey(source, sourceId)
    if (!liveCache.value[key]) {
      liveCache.value[key] = { running: true, cached: 0, total: 0 }
    }
    poll.resume()
  }

  function liveFor(item: LibrarySummary) {
    return liveCache.value[liveCacheKey(item.source, item.source_id)]
  }

  async function load() {
    await loadItems()
    // A page reload shouldn't lose the live "缓存中" state on the shelf.
    await refreshLiveCache()
  }

  async function importComic(payload: ImportRequest) {
    importing.value = true
    importMessage.value = ''
    error.value = ''
    try {
      const result = await api.importComic(payload)
      importMessage.value = result.from_cache
        ? `${result.meta.display_id} 已在本机，没有访问远端`
        : result.background
          ? `${result.meta.display_id} 已收录，页面正在后台缓存`
          : `${result.meta.display_id} 已收录，本次预缓存 ${result.prefetched} 页`
      if (result.warnings.length > 0) {
        importMessage.value += `（${result.warnings.length} 条提醒）`
      }
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
    setFavoriteLocal,
    liveFor,
    startPollingIfActive,
    stopPolling,
  }
})

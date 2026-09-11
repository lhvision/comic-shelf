/**
 * @file useLibrarySync.ts
 * @description 书架多维筛选、URL 查询参数双向联动与服务端流式分页协同 Composable。
 *
 * 核心契约：
 * 1. 监听 activeSource, search, activeTag, favoritesOnly, readingStatus, sortBy, imageSearchResults 变化；
 * 2. 状态正交同步至 URL Query（?status=all|reading|completed & ?favorite=true & ?source=）；
 * 3. 250ms 防抖请求 /api/library 服务端分页并联动刷新 /api/library/facets 全貌统计；
 * 4. 路由初次挂载时支持从 URL 反向还原 readingStatus 与 favoritesOnly；
 * 5. 监听跨标签/跨设备 SSE 事件（import, delete, reconcile）自动同步。
 */

import { watch, type Ref } from 'vue'
import type { Router, RouteLocationNormalizedLoaded } from 'vue-router'
import { useDebounceFn } from '@vueuse/core'
import { useLibraryStore } from '@/stores/library'
import { useSystemEvents } from '@/composables/useSystemEvents'
import type { ReadingStatus, ImageSearchResultItem } from '@/types'
import type { SortKey } from '@/composables/useLibraryFilter'

export interface UseLibrarySyncOptions {
  /** 当前路由对象 */
  route: RouteLocationNormalizedLoaded
  /** 路由器实例 */
  router: Router
  /** 外部激活的数据源 Ref */
  activeSource: Ref<string>
  /** 外部搜索关键词 Ref */
  search: Ref<string>
  /** 外部选中标签 Ref */
  activeTag: Ref<string>
  /** 外部只看喜欢 Ref */
  favoritesOnly: Ref<boolean>
  /** 外部阅读状态单选 Ref */
  readingStatus: Ref<ReadingStatus>
  /** 外部排序方式 Ref */
  sortBy: Ref<SortKey>
  /** 以图搜图结果集（若存在则精准筛选目标漫画） */
  imageSearchResults?: Ref<ImageSearchResultItem[] | null>
  /** 分页拉取单页大小（默认 24） */
  pageSize?: number
  /** 防抖毫秒数（默认 250ms） */
  debounceMs?: number
}

export interface UseLibrarySyncReturn {
  /** 手动触发服务端书架拉取（reset=true 重置回第 1 页；keepLoadedCount=true 在返回视图时按已加载数量刷新） */
  fetchLibrary: (reset?: boolean, keepLoadedCount?: boolean) => Promise<void>
}

export function useLibrarySync(options: UseLibrarySyncOptions): UseLibrarySyncReturn {
  const store = useLibraryStore()
  const { lastLibraryEvent } = useSystemEvents()
  const {
    route,
    router,
    activeSource,
    search,
    activeTag,
    favoritesOnly,
    readingStatus,
    sortBy,
    imageSearchResults,
    pageSize = 24,
    debounceMs = 250,
  } = options

  // 从 URL 初始参数恢复阅读状态与喜欢筛选
  if (route.query.status === 'reading' || route.query.status === 'completed') {
    readingStatus.value = route.query.status
  }
  if (route.query.favorite === 'true') {
    favoritesOnly.value = true
  }

  const fetchLibrary = useDebounceFn(async (reset = true, keepLoadedCount = false) => {
    const hasImageSearch = Boolean(imageSearchResults?.value && imageSearchResults.value.length > 0)
    const targetIds = hasImageSearch
      ? [...new Set(imageSearchResults!.value!.map((r) => `${r.source}:${r.source_id}`))].join(',')
      : undefined

    const effectivePageSize = hasImageSearch
      ? Math.max(pageSize, imageSearchResults!.value!.length)
      : keepLoadedCount && store.items.length > pageSize
        ? Math.min(120, store.items.length)
        : pageSize

    await store.loadItems(false, false, {
      source: activeSource.value || undefined,
      search: hasImageSearch ? undefined : search.value.trim() || undefined,
      tag: activeTag.value || undefined,
      favorite: favoritesOnly.value ? true : undefined,
      status: readingStatus.value,
      sort: sortBy.value,
      page: reset ? 1 : undefined,
      page_size: effectivePageSize,
      ids: targetIds,
    })
    await store.loadFacets(activeSource.value || undefined)
  }, debounceMs)

  watch(
    [activeSource, search, activeTag, favoritesOnly, readingStatus, sortBy],
    ([source, , , fav, status]) => {
      const nextQuery: Record<string, string> = {}
      if (source) nextQuery.source = source
      if (fav) nextQuery.favorite = 'true'
      if (status && status !== 'all') nextQuery.status = status
      router.replace({ query: nextQuery }).catch(() => {})
      void fetchLibrary(true)
    },
  )

  // 监听浏览器前进/后退（PopState）导航，反向对齐 URL 状态与内部筛选 Ref
  watch(
    () => route.query,
    (query) => {
      const qStatus: ReadingStatus =
        query.status === 'reading' || query.status === 'completed' ? query.status : 'all'
      const qFav = query.favorite === 'true'

      let changed = false
      if (readingStatus.value !== qStatus) {
        readingStatus.value = qStatus
        changed = true
      }
      if (favoritesOnly.value !== qFav) {
        favoritesOnly.value = qFav
        changed = true
      }
      if (changed) {
        void fetchLibrary(true)
      }
    },
  )

  if (imageSearchResults) {
    watch(imageSearchResults, () => {
      void fetchLibrary(true)
    })
  }

  watch(lastLibraryEvent, (event) => {
    if (!event) return
    if (
      event.action === 'import' ||
      event.action === 'delete' ||
      event.action === 'reconcile' ||
      event.action === 'metadata_changed'
    ) {
      void fetchLibrary(true)
    }
  })

  return {
    fetchLibrary,
  }
}

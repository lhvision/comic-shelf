/**
 * @file useLibrarySync.ts
 * @description 书架多维筛选状态与服务端流式分页协同 Composable。
 *
 * 核心契约：
 * 1. 监听 activeSource, search, activeTags, favoritesOnly, readingStatus, sortBy, imageSearchResults 变化；
 * 2. 内存单例驱动，零路由污染，杜绝滥用路由 replace 导致顶栏导航被中断取消；
 * 3. 250ms 防抖请求 /api/library 服务端分页并联动刷新 /api/library/facets 全貌统计；
 * 4. 监听跨标签/跨设备 SSE 事件（import, delete, reconcile, metadata_changed）自动同步。
 */

import { watch, type Ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { useLibraryStore } from '@/stores/library'
import { useSystemEvents } from '@/composables/useSystemEvents'
import type { ReadingStatus, ImageSearchResultItem } from '@/types'
import type { SortKey } from '@/composables/useLibraryFilter'

export interface UseLibrarySyncOptions {
  /** 外部激活的数据源 Ref */
  activeSource: Ref<string>
  /** 外部搜索关键词 Ref */
  search: Ref<string>
  /** 外部选中多标签集合 Ref */
  activeTags: Ref<string[]>
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
    activeSource,
    search,
    activeTags,
    favoritesOnly,
    readingStatus,
    sortBy,
    imageSearchResults,
    pageSize = 24,
    debounceMs = 250,
  } = options

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

    const tagsParam = activeTags.value.join(',')
    await store.loadItems(false, false, {
      source: activeSource.value || undefined,
      search: hasImageSearch ? undefined : search.value.trim() || undefined,
      tags: tagsParam || undefined,
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
    [activeSource, search, activeTags, favoritesOnly, readingStatus, sortBy],
    () => {
      void fetchLibrary(true)
    },
    { deep: true },
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

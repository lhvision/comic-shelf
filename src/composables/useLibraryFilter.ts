import { computed, ref, shallowRef, watch, getCurrentScope, onScopeDispose, type Ref } from 'vue'
import type {
  LibrarySummary,
  ImageSearchResultItem,
  ReadingStatus,
  LibraryFacetsResponse,
  SortKey,
} from '@/types'
import { filterAndSortLibrary, type FilterParams } from '@/utils/libraryFilterCore'
import { isCompletedComic, isInProgressComic } from '@/utils/is'
import { sumBy } from '@/utils/math'
import type { WorkerInMessage, WorkerOutMessage } from '@/workers/libraryFilter.worker'

export { isCompletedComic, isInProgressComic }
export type { SortKey }

/**
 * 触发 Web Worker 卸载计算的藏书规模阈值。
 * 藏书少于 1000 本时，主线程 O(N) 过滤耗时 < 1ms，直接同步计算以换取极致响应；
 * 藏书达到或超过 1000 本且环境支持 Worker 时，自动切入 Worker 线程避免掉帧。
 */
export const WORKER_THRESHOLD = 1000

export interface UseLibraryFilterOptions {
  /** 外部共享的搜索关键词 Ref（用于跨路由状态记忆） */
  search?: Ref<string>
  /** 外部共享的多标签集合 Ref */
  activeTags?: Ref<string[]>
  /** 外部共享的只看喜欢 Ref */
  favoritesOnly?: Ref<boolean>
  /** 外部共享的阅读状态单选维度 Ref */
  readingStatus?: Ref<ReadingStatus>
  /** 外部共享的全局 Facets 统计数据 Ref */
  facets?: Ref<LibraryFacetsResponse | null>
  /** 外部共享的排序规则 Ref */
  sortBy?: Ref<SortKey>
}

/**
 * 书架筛选与检索 Composable：
 * 负责来源过滤、关键词模糊检索、标签过滤、只看喜欢、阅读状态筛选与多模式排序。
 *
 * 核心架构特性：
 * 1. 采用纯函数双轨架构：小规模藏书主线程纯函数同步运行，万级藏书无感卸载至 Web Worker；
 * 2. 线程通信极简收敛：仅单向同步轻量 ID 数组（string[]），主线程 O(1) 映射还原，杜绝结构化克隆风暴；
 * 3. 完美兼容 SSR 与 Vitest 无 DOM/Worker 纯 Node 环境。
 *
 * @param items 藏书全量汇总列表 Ref
 * @param activeSource 当前选中的漫画源过滤 Ref（空字符串表示全部源）
 * @param imageSearchResults 以图搜图检索结果 Ref（可选）
 * @param options 外部状态注入选项
 */
export function useLibraryFilter(
  items: Ref<LibrarySummary[]>,
  activeSource: Ref<string>,
  imageSearchResults?: Ref<ImageSearchResultItem[] | null>,
  options?: UseLibraryFilterOptions,
) {
  const search = options?.search ?? ref('')
  const activeTags = options?.activeTags ?? ref<string[]>([])
  const favoritesOnly = options?.favoritesOnly ?? ref(false)
  const readingStatus = options?.readingStatus ?? ref<ReadingStatus>('all')
  const sortBy = options?.sortBy ?? ref<SortKey>('recent')

  const sourceItems = computed(() => {
    const list = Array.isArray(items?.value) ? items.value.filter(Boolean) : []
    return activeSource.value ? list.filter((item) => item.source === activeSource.value) : list
  })

  const totalBooks = computed(
    () => options?.facets?.value?.stats?.total_books ?? sourceItems.value.length,
  )

  const totalPages = computed(
    () =>
      options?.facets?.value?.stats?.total_pages ??
      sumBy(sourceItems.value, (item) => item?.page_count ?? 0),
  )

  const totalCachedPages = computed(
    () =>
      options?.facets?.value?.stats?.cached_pages ??
      sumBy(sourceItems.value, (item) => item?.cached_pages ?? 0),
  )

  const tagCounts = computed<Array<[string, number]>>(() => {
    if (options?.facets?.value?.top_tags && options.facets.value.top_tags.length > 0) {
      return options.facets.value.top_tags.slice(0, 18)
    }
    const counts = new Map<string, number>()
    for (const item of sourceItems.value) {
      if (!item || !Array.isArray(item.tags)) continue
      for (const tag of item.tags) {
        counts.set(tag, (counts.get(tag) ?? 0) + 1)
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 18)
  })

  // { source_sourceId: { bestMatchPage: number, bestScore: number } }
  const imageSearchMatchMap = computed(() => {
    const map = new Map<string, { bestMatchPage: number; bestScore: number }>()
    if (!imageSearchResults?.value) return map

    for (const res of imageSearchResults.value) {
      if (!res) continue
      const key = `${res.source}_${res.source_id}`
      const existing = map.get(key)
      if (!existing || res.score > existing.bestScore) {
        map.set(key, { bestMatchPage: res.page_index, bestScore: res.score })
      }
    }
    return map
  })

  // 以图搜图轻量化结构（供 Worker / 纯函数过滤）
  const imageSearchMatchesRecord = computed<Record<string, number> | undefined>(() => {
    if (!imageSearchResults?.value || imageSearchResults.value.length === 0) return undefined
    const record: Record<string, number> = {}
    for (const res of imageSearchResults.value) {
      if (!res) continue
      const key = `${res.source}_${res.source_id}`
      if (res.score > (record[key] ?? -1)) {
        record[key] = res.score
      }
    }
    return record
  })

  // 聚合筛选参数对象
  const filterParams = computed<FilterParams>(() => ({
    activeSource: activeSource.value,
    search: search.value,
    activeTags: activeTags.value,
    favoritesOnly: favoritesOnly.value,
    readingStatus: readingStatus.value,
    sortBy: sortBy.value,
    imageSearchMatches: imageSearchMatchesRecord.value,
  }))

  // 藏书快速 O(1) ID 查找表
  const itemMap = computed(() => {
    const map = new Map<string, LibrarySummary>()
    const list = Array.isArray(items?.value) ? items.value : []
    for (const item of list) {
      if (item) {
        map.set(`${item.source}:${item.source_id}`, item)
      }
    }
    return map
  })

  const isWorkerSupported = typeof Worker !== 'undefined'
  const isLargeLibrary = computed(
    () => isWorkerSupported && (items.value?.length ?? 0) >= WORKER_THRESHOLD,
  )

  // Worker 异步检索出的结果（采用 shallowRef 杜绝大规模条目代理）
  const workerFiltered = shallowRef<LibrarySummary[]>([])
  let workerInstance: Worker | null = null
  let currentRequestId = 0

  function ensureWorker(): Worker | null {
    if (!isWorkerSupported) return null
    if (!workerInstance) {
      workerInstance = new Worker(new URL('@/workers/libraryFilter.worker.ts', import.meta.url), {
        type: 'module',
      })
      workerInstance.onmessage = (event: MessageEvent<WorkerOutMessage>) => {
        const data = event.data
        if (data?.type === 'result' && data.requestId === currentRequestId) {
          const map = itemMap.value
          workerFiltered.value = data.idList
            .map((id) => map.get(id))
            .filter((x): x is LibrarySummary => Boolean(x))
        }
      }
    }
    return workerInstance
  }

  function triggerWorkerFilter() {
    if (!isLargeLibrary.value) return
    const worker = ensureWorker()
    if (worker) {
      const reqId = ++currentRequestId
      const filterMsg: WorkerInMessage = {
        type: 'filter',
        params: filterParams.value,
        requestId: reqId,
      }
      worker.postMessage(filterMsg)
    }
  }

  // 万级藏书场景下监听 items 变化，全量同步至 Worker 内存并即刻触发初次/更新过滤
  watch(
    () => items.value,
    (newItems) => {
      if (!isLargeLibrary.value) return
      const worker = ensureWorker()
      if (worker) {
        const syncMsg: WorkerInMessage = {
          type: 'sync',
          items: newItems,
        }
        worker.postMessage(syncMsg)
        triggerWorkerFilter()
      }
    },
    { immediate: true },
  )

  // 万级藏书场景下监听过滤条件变化，向 Worker 发起检索请求
  watch(filterParams, () => {
    triggerWorkerFilter()
  })

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (workerInstance) {
        workerInstance.terminate()
        workerInstance = null
      }
    })
  }

  const filtered = computed(() => {
    // 超过阈值时消费 Worker 异步排序结果
    if (isLargeLibrary.value) {
      // 若 Worker 尚未回传第一帧（如初始挂载瞬时），先回退到前 60 本轻量切片保障首屏瞬开不闪烁
      if (workerFiltered.value.length === 0 && (items.value?.length ?? 0) > 0) {
        return filterAndSortLibrary(items.value.slice(0, 60), filterParams.value)
      }
      return workerFiltered.value
    }

    // <1000 本或 Node/Vitest 环境：主线程极速纯函数同步运算
    return filterAndSortLibrary(items.value || [], filterParams.value)
  })

  return {
    search,
    activeTags,
    favoritesOnly,
    readingStatus,
    sortBy,
    sourceItems,
    totalBooks,
    totalPages,
    totalCachedPages,
    tagCounts,
    imageSearchMatchMap,
    filtered,
  }
}

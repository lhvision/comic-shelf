import { computed, ref, type Ref } from 'vue'
import type {
  LibrarySummary,
  ImageSearchResultItem,
  ReadingStatus,
  LibraryFacetsResponse,
} from '@/types'

export type SortKey = 'recent' | 'title' | 'pages' | 'cached'

/**
 * 判定一本藏书是否已被当前用户完全翻阅读完
 */
export function isCompletedComic(item: LibrarySummary): boolean {
  return (item.last_page ?? 0) >= item.page_count && item.page_count > 0
}

/**
 * 判定一本藏书是否处于在读状态（翻阅过但未完全读完）
 */
export function isInProgressComic(item: LibrarySummary): boolean {
  return (item.last_page ?? 0) > 0 && (item.last_page ?? 0) < item.page_count && item.page_count > 0
}

export interface UseLibraryFilterOptions {
  /** 外部共享的搜索关键词 Ref（用于跨路由状态记忆） */
  search?: Ref<string>
  /** 外部共享的选中标签 Ref */
  activeTag?: Ref<string>
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
 * 负责来源过滤、关键词模糊检索、标签过滤、只看喜欢与多模式排序。
 */
export function useLibraryFilter(
  items: Ref<LibrarySummary[]>,
  activeSource: Ref<string>,
  imageSearchResults?: Ref<ImageSearchResultItem[] | null>,
  options?: UseLibraryFilterOptions,
) {
  const search = options?.search ?? ref('')
  const activeTag = options?.activeTag ?? ref('')
  const favoritesOnly = options?.favoritesOnly ?? ref(false)
  const readingStatus = options?.readingStatus ?? ref<ReadingStatus>('all')
  const sortBy = options?.sortBy ?? ref<SortKey>('recent')

  const sourceItems = computed(() => {
    const list = Array.isArray(items?.value) ? items.value : []
    return activeSource.value
      ? list.filter((item) => item && item.source === activeSource.value)
      : list
  })

  const totalBooks = computed(
    () => options?.facets?.value?.stats?.total_books ?? sourceItems.value.length,
  )

  const totalPages = computed(
    () =>
      options?.facets?.value?.stats?.total_pages ??
      sourceItems.value.reduce((sum, item) => sum + (item?.page_count ?? 0), 0),
  )

  const totalCachedPages = computed(
    () =>
      options?.facets?.value?.stats?.cached_pages ??
      sourceItems.value.reduce((sum, item) => sum + (item?.cached_pages ?? 0), 0),
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

  const filtered = computed(() => {
    const needle = search.value.trim().toLocaleLowerCase()

    // First, base filter by search text, tag, favorite, reading status
    let list = sourceItems.value.filter((item) => {
      const matchSearch =
        needle.length === 0 ||
        item.title.toLocaleLowerCase().includes(needle) ||
        item.display_id.toLocaleLowerCase().includes(needle) ||
        item.authors.some((value) => value.toLocaleLowerCase().includes(needle)) ||
        item.works.some((value) => value.toLocaleLowerCase().includes(needle)) ||
        item.actors.some((value) => value.toLocaleLowerCase().includes(needle)) ||
        item.tags.some((value) => value.toLocaleLowerCase().includes(needle)) ||
        // T11 规范：让「第 5 话」等章节标题也能命中前端书架搜索，与服务端 SQL LIKE 对齐
        Boolean(item.chapter_titles?.some((value) => value.toLocaleLowerCase().includes(needle)))

      const matchTag = activeTag.value === '' || item.tags.includes(activeTag.value)
      const matchFavorite = !favoritesOnly.value || item.favorite
      const matchStatus =
        readingStatus.value === 'all'
          ? true
          : readingStatus.value === 'reading'
            ? isInProgressComic(item)
            : readingStatus.value === 'completed'
              ? isCompletedComic(item)
              : (item.last_page ?? 0) === 0

      // If we have image search results, it must also be in the matches
      let matchImageSearch = true
      if (imageSearchResults?.value) {
        const key = `${item.source}_${item.source_id}`
        matchImageSearch = imageSearchMatchMap.value.has(key)
      }

      return matchSearch && matchTag && matchFavorite && matchStatus && matchImageSearch
    })

    list = [...list]

    // If image search results exist, override sorting to sort by score descending
    if (imageSearchResults?.value) {
      list.sort((a, b) => {
        const scoreA = imageSearchMatchMap.value.get(`${a.source}_${a.source_id}`)?.bestScore || 0
        const scoreB = imageSearchMatchMap.value.get(`${b.source}_${b.source_id}`)?.bestScore || 0
        return scoreB - scoreA
      })
    } else {
      switch (sortBy.value) {
        case 'title':
          list.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'))
          break
        case 'pages':
          list.sort((a, b) => b.page_count - a.page_count)
          break
        case 'cached':
          list.sort(
            (a, b) =>
              b.cached_pages / Math.max(b.page_count, 1) -
              a.cached_pages / Math.max(a.page_count, 1),
          )
          break
        default: {
          const activeList = list.filter((item) => !isCompletedComic(item))
          const completedList = list.filter((item) => isCompletedComic(item))
          const sortByImportedDesc = (a: LibrarySummary, b: LibrarySummary) =>
            new Date(b.imported_at || 0).getTime() - new Date(a.imported_at || 0).getTime()
          activeList.sort(sortByImportedDesc)
          completedList.sort(sortByImportedDesc)
          list = [...activeList, ...completedList]
          break
        }
      }
    }
    return list
  })

  function setSort(value: string) {
    sortBy.value = value as SortKey
  }

  return {
    search,
    activeTag,
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
    setSort,
  }
}

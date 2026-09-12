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
const zhCollator = new Intl.Collator('zh-CN')

/**
 * 缓存每本漫画的小写搜索文本组合（WeakMap 随藏书对象生命周期自愈回收），
 * 彻底消除每次按键对 tags / authors / works / chapter_titles 的万次重复数组遍历与字符串转换。
 */
const itemSearchTextCache = new WeakMap<LibrarySummary, string>()

function getSearchText(item: LibrarySummary): string {
  if (!item) return ''
  let cached = itemSearchTextCache.get(item)
  if (cached !== undefined) return cached

  const parts = [
    item.title || '',
    item.display_id || '',
    ...(item.authors || []),
    ...(item.works || []),
    ...(item.actors || []),
    ...(item.tags || []),
    ...(item.chapter_titles || []),
  ]
  // 采用换行符作为分隔符，杜绝关键词跨字段边界意外连词匹配
  cached = parts.join('\n').toLocaleLowerCase()
  itemSearchTextCache.set(item, cached)
  return cached
}

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
      const matchSearch = needle.length === 0 || getSearchText(item).includes(needle)

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
          list.sort((a, b) => zhCollator.compare(a.title, b.title))
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
          const activeList: LibrarySummary[] = []
          const completedList: LibrarySummary[] = []
          const timeMap = new Map<LibrarySummary, number>()

          for (const item of list) {
            if (isCompletedComic(item)) {
              completedList.push(item)
            } else {
              activeList.push(item)
            }
            timeMap.set(item, item.imported_at ? Date.parse(item.imported_at) || 0 : 0)
          }

          const sortByImportedDesc = (a: LibrarySummary, b: LibrarySummary) =>
            (timeMap.get(b) ?? 0) - (timeMap.get(a) ?? 0)

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

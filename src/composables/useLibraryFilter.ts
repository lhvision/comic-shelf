import { computed, ref, type Ref } from 'vue'
import type { LibrarySummary, ImageSearchResultItem } from '@/types'

export type SortKey = 'recent' | 'title' | 'pages' | 'cached'

/**
 * 书架筛选与检索 Composable：
 * 负责来源过滤、关键词模糊检索、标签过滤、只看喜欢与多模式排序。
 */
export function useLibraryFilter(
  items: Ref<LibrarySummary[]>,
  activeSource: Ref<string>,
  imageSearchResults?: Ref<ImageSearchResultItem[] | null>,
) {
  const search = ref('')
  const activeTag = ref('')
  const favoritesOnly = ref(false)
  const sortBy = ref<SortKey>('recent')

  const sourceItems = computed(() =>
    activeSource.value
      ? items.value.filter((item) => item.source === activeSource.value)
      : items.value,
  )

  const totalPages = computed(() =>
    sourceItems.value.reduce((sum, item) => sum + item.page_count, 0),
  )

  const totalCachedPages = computed(() =>
    sourceItems.value.reduce((sum, item) => sum + item.cached_pages, 0),
  )

  const tagCounts = computed<Array<[string, number]>>(() => {
    const counts = new Map<string, number>()
    for (const item of sourceItems.value) {
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

    // First, base filter by search text, tag, favorite
    let list = sourceItems.value.filter((item) => {
      const matchSearch =
        needle.length === 0 ||
        item.title.toLocaleLowerCase().includes(needle) ||
        item.display_id.toLocaleLowerCase().includes(needle) ||
        item.authors.some((value) => value.toLocaleLowerCase().includes(needle)) ||
        item.works.some((value) => value.toLocaleLowerCase().includes(needle)) ||
        item.actors.some((value) => value.toLocaleLowerCase().includes(needle)) ||
        item.tags.some((value) => value.toLocaleLowerCase().includes(needle))

      const matchTag = activeTag.value === '' || item.tags.includes(activeTag.value)
      const matchFavorite = !favoritesOnly.value || item.favorite

      // If we have image search results, it must also be in the matches
      let matchImageSearch = true
      if (imageSearchResults?.value) {
        const key = `${item.source}_${item.source_id}`
        matchImageSearch = imageSearchMatchMap.value.has(key)
      }

      return matchSearch && matchTag && matchFavorite && matchImageSearch
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
        default:
          list.sort(
            (a, b) =>
              new Date(b.imported_at || 0).getTime() - new Date(a.imported_at || 0).getTime(),
          )
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
    sortBy,
    sourceItems,
    totalPages,
    totalCachedPages,
    tagCounts,
    imageSearchMatchMap,
    filtered,
    setSort,
  }
}

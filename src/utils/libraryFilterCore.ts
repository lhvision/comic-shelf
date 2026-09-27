/**
 * @file libraryFilterCore.ts
 * @description 书架多维检索与排序核心纯函数（主线程与 Web Worker 共享）。
 */

import type { LibrarySummary, ReadingStatus, SortKey } from '@/types'

export function isCompletedComic(item: LibrarySummary | null | undefined): boolean {
  if (!item) return false
  return (item.last_page ?? 0) >= item.page_count && item.page_count > 0
}

export function isInProgressComic(item: LibrarySummary | null | undefined): boolean {
  if (!item) return false
  return (item.last_page ?? 0) > 0 && (item.last_page ?? 0) < item.page_count && item.page_count > 0
}

export function isLocalComic(source: string | null | undefined): boolean {
  return source === 'local'
}

export function isPicacgComic(source: string | null | undefined): boolean {
  return source === 'picacg'
}

export function isJmComic(source: string | null | undefined): boolean {
  return source === 'jm'
}

const zhCollator = new Intl.Collator('zh-CN', { numeric: true })

const itemSearchTextCache = new WeakMap<LibrarySummary, string>()

export function getSearchText(item: LibrarySummary): string {
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
  cached = parts.join('\n').toLocaleLowerCase()
  itemSearchTextCache.set(item, cached)
  return cached
}

export type SearchScope = 'all' | 'title_id' | 'id' | 'author' | 'tag'

export interface FilterParams {
  activeSource: string
  search: string
  searchScope?: SearchScope
  activeTags?: string[]
  favoritesOnly: boolean
  readingStatus: ReadingStatus
  sortBy: SortKey
  imageSearchMatches?: Record<string, number>
}

function getRelevanceTier(item: LibrarySummary, needle: string): number {
  const title = (item.title || '').toLowerCase()
  const displayId = (item.display_id || '').toLowerCase()
  const sourceId = (item.source_id || '').toLowerCase()

  // Tier 0: 完全匹配标题或车号
  if (title === needle || displayId === needle || sourceId === needle) {
    return 0
  }
  // Tier 1: 标题包含关键词
  if (title.includes(needle)) {
    return 1
  }
  // Tier 2: 作者包含关键词
  if (Array.isArray(item.authors) && item.authors.some((a) => a.toLowerCase().includes(needle))) {
    return 2
  }
  // Tier 3: 标签/原作/角色/章节标题等包含关键词
  return 3
}

export function filterAndSortLibrary(
  items: LibrarySummary[],
  params: FilterParams,
): LibrarySummary[] {
  const needle = params.search.trim().toLocaleLowerCase()
  const activeSource = params.activeSource
  const rawTags = params.activeTags ?? []
  const activeTags = rawTags
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 5)
  const favoritesOnly = params.favoritesOnly
  const readingStatus = params.readingStatus
  const sortBy = params.sortBy
  const imageSearchMatches = params.imageSearchMatches
  const searchScope = params.searchScope ?? 'all'

  let list = Array.isArray(items) ? items.filter(Boolean) : []
  if (activeSource) {
    list = list.filter((item) => item && item.source === activeSource)
  }

  list = list.filter((item) => {
    if (!item) return false

    let matchSearch = true
    if (needle.length > 0) {
      if (searchScope === 'id') {
        const dId = (item.display_id || '').toLowerCase()
        const sId = (item.source_id || '').toLowerCase()
        matchSearch = dId.includes(needle) || sId.includes(needle)
      } else if (searchScope === 'title_id') {
        const title = (item.title || '').toLowerCase()
        const dId = (item.display_id || '').toLowerCase()
        const sId = (item.source_id || '').toLowerCase()
        matchSearch = title.includes(needle) || dId.includes(needle) || sId.includes(needle)
      } else if (searchScope === 'author') {
        matchSearch =
          Array.isArray(item.authors) && item.authors.some((a) => a.toLowerCase().includes(needle))
      } else if (searchScope === 'tag') {
        matchSearch =
          Array.isArray(item.tags) && item.tags.some((t) => t.toLowerCase().includes(needle))
      } else {
        matchSearch = getSearchText(item).includes(needle)
      }
    }

    const matchTag = activeTags.every((t) => Array.isArray(item.tags) && item.tags.includes(t))
    const matchFavorite = !favoritesOnly || item.favorite
    const matchStatus =
      readingStatus === 'all'
        ? true
        : readingStatus === 'reading'
          ? isInProgressComic(item)
          : readingStatus === 'completed'
            ? isCompletedComic(item)
            : (item.last_page ?? 0) === 0

    let matchImageSearch = true
    if (imageSearchMatches) {
      const key = `${item.source}_${item.source_id}`
      matchImageSearch = key in imageSearchMatches
    }

    return matchSearch && matchTag && matchFavorite && matchStatus && matchImageSearch
  })

  if (imageSearchMatches) {
    list.sort((a, b) => {
      const scoreA = imageSearchMatches[`${a.source}_${a.source_id}`] || 0
      const scoreB = imageSearchMatches[`${b.source}_${b.source_id}`] || 0
      return scoreB - scoreA
    })
  } else {
    const timeMap = new Map<LibrarySummary, number>()
    if (sortBy === 'recent' || (needle.length > 0 && searchScope === 'all')) {
      for (const item of list) {
        timeMap.set(item, item.imported_at ? Date.parse(item.imported_at) || 0 : 0)
      }
    }

    const compareBySortKey = (a: LibrarySummary, b: LibrarySummary): number => {
      switch (sortBy) {
        case 'title':
          return zhCollator.compare(a.title, b.title)
        case 'pages':
          return b.page_count - a.page_count
        case 'cached':
          return (
            b.cached_pages / Math.max(b.page_count, 1) - a.cached_pages / Math.max(a.page_count, 1)
          )
        default: {
          const aCompleted = isCompletedComic(a) ? 1 : 0
          const bCompleted = isCompletedComic(b) ? 1 : 0
          if (aCompleted !== bCompleted) {
            return aCompleted - bCompleted
          }
          return (timeMap.get(b) ?? 0) - (timeMap.get(a) ?? 0)
        }
      }
    }

    if (needle.length > 0 && searchScope === 'all') {
      const tierMap = new Map<LibrarySummary, number>()
      for (const item of list) {
        tierMap.set(item, getRelevanceTier(item, needle))
      }
      list.sort((a, b) => {
        const tierA = tierMap.get(a) ?? 3
        const tierB = tierMap.get(b) ?? 3
        if (tierA !== tierB) {
          return tierA - tierB
        }
        return compareBySortKey(a, b)
      })
    } else {
      list.sort(compareBySortKey)
    }
  }

  return list
}

export function filterAndSortLibraryIds(items: LibrarySummary[], params: FilterParams): string[] {
  const result = filterAndSortLibrary(items, params)
  return result.map((item) => `${item.source}:${item.source_id}`)
}

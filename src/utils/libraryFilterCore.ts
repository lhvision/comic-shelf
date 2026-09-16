/**
 * @file libraryFilterCore.ts
 * @description 书架多维检索与排序核心纯函数（主线程与 Web Worker 共享）。
 */

import type { LibrarySummary, ReadingStatus } from '@/types'
import type { SortKey } from '@/composables/useLibraryFilter'

export function isCompletedComic(item: LibrarySummary | null | undefined): boolean {
  if (!item) return false
  return (item.last_page ?? 0) >= item.page_count && item.page_count > 0
}

export function isInProgressComic(item: LibrarySummary | null | undefined): boolean {
  if (!item) return false
  return (item.last_page ?? 0) > 0 && (item.last_page ?? 0) < item.page_count && item.page_count > 0
}

export function isUnreadComic(item: LibrarySummary | null | undefined): boolean {
  if (!item) return false
  return (item.last_page ?? 0) === 0 || !item.last_page
}

export function isMultiChapterComic(item: { chapters?: unknown[] } | null | undefined): boolean {
  return Array.isArray(item?.chapters) && item.chapters.length > 1
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

export interface FilterParams {
  activeSource: string
  search: string
  activeTag: string
  favoritesOnly: boolean
  readingStatus: ReadingStatus
  sortBy: SortKey
  imageSearchMatches?: Record<string, number>
}

export function filterAndSortLibrary(
  items: LibrarySummary[],
  params: FilterParams,
): LibrarySummary[] {
  const needle = params.search.trim().toLocaleLowerCase()
  const activeSource = params.activeSource
  const activeTag = params.activeTag
  const favoritesOnly = params.favoritesOnly
  const readingStatus = params.readingStatus
  const sortBy = params.sortBy
  const imageSearchMatches = params.imageSearchMatches

  let list = Array.isArray(items) ? items.filter(Boolean) : []
  if (activeSource) {
    list = list.filter((item) => item && item.source === activeSource)
  }

  list = list.filter((item) => {
    if (!item) return false
    const matchSearch = needle.length === 0 || getSearchText(item).includes(needle)
    const matchTag = activeTag === '' || item.tags.includes(activeTag)
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

  list = [...list]

  if (imageSearchMatches) {
    list.sort((a, b) => {
      const scoreA = imageSearchMatches[`${a.source}_${a.source_id}`] || 0
      const scoreB = imageSearchMatches[`${b.source}_${b.source_id}`] || 0
      return scoreB - scoreA
    })
  } else {
    switch (sortBy) {
      case 'title':
        list.sort((a, b) => zhCollator.compare(a.title, b.title))
        break
      case 'pages':
        list.sort((a, b) => b.page_count - a.page_count)
        break
      case 'cached':
        list.sort(
          (a, b) =>
            b.cached_pages / Math.max(b.page_count, 1) - a.cached_pages / Math.max(a.page_count, 1),
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
      }
    }
  }

  return list
}

export function filterAndSortLibraryIds(items: LibrarySummary[], params: FilterParams): string[] {
  const result = filterAndSortLibrary(items, params)
  return result.map((item) => `${item.source}:${item.source_id}`)
}

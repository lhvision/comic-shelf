import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { useShelfState, DEFAULT_SHELF_BATCH } from '@/composables/useShelfState'

describe('useShelfState composable', () => {
  const shelf = useShelfState()

  beforeEach(() => {
    shelf.resetAllShelfState()
  })

  it('initializes with default state values', () => {
    expect(shelf.shelfScrollY.value).toBe(0)
    expect(shelf.activeUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
    expect(shelf.archiveOpen.value).toBe(false)
    expect(shelf.search.value).toBe('')
    expect(shelf.activeTags.value).toEqual([])
    expect(shelf.favoritesOnly.value).toBe(false)
    expect(shelf.readingStatus.value).toBe('all')
    expect(shelf.sortBy.value).toBe('recent')
    expect(shelf.hasActiveFilters.value).toBe(false)
  })

  it('updates and resets scroll and unfold states', () => {
    shelf.saveScrollPosition(450)
    expect(shelf.shelfScrollY.value).toBe(450)

    shelf.saveScrollPosition(-50)
    expect(shelf.shelfScrollY.value).toBe(0)

    shelf.resetShelfScroll()
    expect(shelf.shelfScrollY.value).toBe(0)

    shelf.activeUnfoldCount.value = 48
    shelf.archiveOpen.value = true
    shelf.resetShelfUnfolds()
    expect(shelf.activeUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
    expect(shelf.archiveOpen.value).toBe(false)
  })

  it('detects hasActiveFilters reactively', () => {
    expect(shelf.hasActiveFilters.value).toBe(false)

    shelf.activeTags.value = ['同人']
    expect(shelf.hasActiveFilters.value).toBe(true)
    shelf.activeTags.value = []

    shelf.favoritesOnly.value = true
    expect(shelf.hasActiveFilters.value).toBe(true)
    shelf.favoritesOnly.value = false

    shelf.readingStatus.value = 'reading'
    expect(shelf.hasActiveFilters.value).toBe(true)
    shelf.readingStatus.value = 'all'

    shelf.search.value = '东方'
    expect(shelf.hasActiveFilters.value).toBe(true)
    shelf.search.value = ''

    shelf.sortBy.value = 'cached'
    expect(shelf.hasActiveFilters.value).toBe(true)
    shelf.sortBy.value = 'recent'

    expect(shelf.hasActiveFilters.value).toBe(false)
  })

  describe('hydrateFromQuery', () => {
    it('returns false when query has no matching fields', () => {
      const result = shelf.hydrateFromQuery({})
      expect(result).toBe(false)
      expect(shelf.hasActiveFilters.value).toBe(false)
    })

    it('hydrates string tags and caps at 5', () => {
      const result = shelf.hydrateFromQuery({ tags: 'tag1, tag2, tag3, tag4, tag5, tag6' })
      expect(result).toBe(true)
      expect(shelf.activeTags.value).toEqual(['tag1', 'tag2', 'tag3', 'tag4', 'tag5'])
    })

    it('hydrates single tag query', () => {
      const result = shelf.hydrateFromQuery({ tag: '全彩' })
      expect(result).toBe(true)
      expect(shelf.activeTags.value).toEqual(['全彩'])
    })

    it('hydrates array tags', () => {
      const result = shelf.hydrateFromQuery({ tags: ['东方', '同人'] })
      expect(result).toBe(true)
      expect(shelf.activeTags.value).toEqual(['东方', '同人'])
    })

    it('hydrates reading status', () => {
      expect(shelf.hydrateFromQuery({ status: 'completed' })).toBe(true)
      expect(shelf.readingStatus.value).toBe('completed')

      expect(shelf.hydrateFromQuery({ status: 'reading' })).toBe(true)
      expect(shelf.readingStatus.value).toBe('reading')
    })

    it('hydrates favorites with true or 1', () => {
      shelf.hydrateFromQuery({ favorite: 'true' })
      expect(shelf.favoritesOnly.value).toBe(true)

      shelf.favoritesOnly.value = false
      shelf.hydrateFromQuery({ fav: '1' })
      expect(shelf.favoritesOnly.value).toBe(true)
    })

    it('hydrates search keyword via q or search', () => {
      shelf.hydrateFromQuery({ q: '东方Project ' })
      expect(shelf.search.value).toBe('东方Project')

      shelf.hydrateFromQuery({ search: '科幻' })
      expect(shelf.search.value).toBe('科幻')
    })

    it('hydrates sort key', () => {
      shelf.hydrateFromQuery({ sort: 'cached' })
      expect(shelf.sortBy.value).toBe('cached')
    })
  })

  describe('buildShareUrl', () => {
    it('returns base path when no active filters', () => {
      const url = shelf.buildShareUrl('https://paper.example.com')
      expect(url).toBe('https://paper.example.com')
    })

    it('includes source, q, tags, favorite, status, and sort when active', () => {
      shelf.search.value = '魔女'
      shelf.activeTags.value = ['全彩', '连载']
      shelf.favoritesOnly.value = true
      shelf.readingStatus.value = 'reading'
      shelf.sortBy.value = 'title'

      const url = shelf.buildShareUrl('https://paper.example.com/', 'jm')
      expect(url).toContain('source=jm')
      expect(url).toContain('q=%E9%AD%94%E5%A5%B3')
      expect(url).toContain('tags=%E5%85%A8%E5%BD%A9%2C%E8%BF%9E%E8%BD%BD')
      expect(url).toContain('favorite=true')
      expect(url).toContain('status=reading')
      expect(url).toContain('sort=title')
    })

    it('excludes default status and sort values from share url', () => {
      shelf.readingStatus.value = 'all'
      shelf.sortBy.value = 'recent'
      shelf.activeTags.value = ['单行本']

      const url = shelf.buildShareUrl('https://paper.example.com')
      expect(url).not.toContain('status=')
      expect(url).not.toContain('sort=')
      expect(url).toContain('tags=%E5%8D%95%E8%A1%8C%E6%9C%AC')
    })
  })
})

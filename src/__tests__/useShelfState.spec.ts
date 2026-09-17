import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { useShelfState, DEFAULT_SHELF_BATCH } from '@/composables/useShelfState'

describe('useShelfState', () => {
  beforeEach(() => {
    const state = useShelfState()
    state.resetAllShelfState()
  })

  it('initializes with default values', () => {
    const state = useShelfState()
    expect(state.shelfScrollY.value).toBe(0)
    expect(state.activeUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
    expect(state.archiveOpen.value).toBe(false)
    expect(state.archiveUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
    expect(state.unifiedUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
    expect(state.search.value).toBe('')
    expect(state.activeTag.value).toBe('')
    expect(state.activeTags.value).toEqual([])
    expect(state.favoritesOnly.value).toBe(false)
    expect(state.readingStatus.value).toBe('all')
    expect(state.sortBy.value).toBe('recent')
    expect(state.tagTrayExpanded.value).toBe(false)
  })

  it('supports activeTags and provides bidirectional bridge with activeTag', () => {
    const state = useShelfState()
    expect(state.activeTags.value).toEqual([])
    expect(state.activeTag.value).toBe('')

    // Set via activeTags
    state.activeTags.value = ['同人', '全彩']
    expect(state.activeTag.value).toBe('同人')

    // Set via activeTag
    state.activeTag.value = '汉化'
    expect(state.activeTags.value).toEqual(['汉化'])

    // Clear via activeTag
    state.activeTag.value = ''
    expect(state.activeTags.value).toEqual([])

    // Clear via resetAllShelfState
    state.activeTags.value = ['tagA', 'tagB']
    state.resetAllShelfState()
    expect(state.activeTags.value).toEqual([])
    expect(state.activeTag.value).toBe('')
  })

  it('saves and resets scroll position', () => {
    const state = useShelfState()
    state.saveScrollPosition(850)
    expect(state.shelfScrollY.value).toBe(850)

    // Negative values should be clamped to 0
    state.saveScrollPosition(-50)
    expect(state.shelfScrollY.value).toBe(0)

    state.saveScrollPosition(400)
    state.resetShelfScroll()
    expect(state.shelfScrollY.value).toBe(0)
  })

  it('maintains unfold counts and drawer state across calls', () => {
    const state1 = useShelfState()
    state1.activeUnfoldCount.value = 36
    state1.archiveOpen.value = true
    state1.archiveUnfoldCount.value = 24

    const state2 = useShelfState()
    expect(state2.activeUnfoldCount.value).toBe(36)
    expect(state2.archiveOpen.value).toBe(true)
    expect(state2.archiveUnfoldCount.value).toBe(24)

    state2.resetShelfUnfolds()
    expect(state2.activeUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
    expect(state2.archiveOpen.value).toBe(false)
    expect(state2.archiveUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
  })

  it('maintains filters and resets all shelf state cleanly', () => {
    const state = useShelfState()
    state.search.value = '夏日'
    state.activeTag.value = '同人'
    state.favoritesOnly.value = true
    state.readingStatus.value = 'completed'
    state.sortBy.value = 'pages'
    state.tagTrayExpanded.value = true
    state.saveScrollPosition(1200)
    state.activeUnfoldCount.value = 48

    state.resetAllShelfState()

    expect(state.shelfScrollY.value).toBe(0)
    expect(state.activeUnfoldCount.value).toBe(DEFAULT_SHELF_BATCH)
    expect(state.search.value).toBe('')
    expect(state.activeTag.value).toBe('')
    expect(state.favoritesOnly.value).toBe(false)
    expect(state.readingStatus.value).toBe('all')
    expect(state.sortBy.value).toBe('recent')
    expect(state.tagTrayExpanded.value).toBe(false)
  })
})

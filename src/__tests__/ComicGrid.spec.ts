import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ComicGrid from '@/components/library/ComicGrid.vue'
import type { LibrarySummary } from '@/types'

// Mock subcomponents
vi.mock('@/components/ComicCard.vue', () => ({
  default: {
    name: 'ComicCard',
    props: ['comic', 'cache', 'searchMatch'],
    template: '<div class="mock-comic-card">{{ comic.title }}</div>',
  },
}))

function makeComics(count: number): LibrarySummary[] {
  return Array.from({ length: count }, (_, i) => ({
    source: 'jm',
    source_id: `id_${i + 1}`,
    display_id: `${i + 1}`,
    title: `漫画标题 ${i + 1}`,
    cover_paths: ['/cover1.webp', '/cover2.webp', '/cover3.webp', '/cover4.webp'],
    page_count: 20,
    cached_pages: 20,
    favorite: false,
    authors: ['作者'],
    works: [],
    actors: [],
    tags: ['同人'],
    views: '100',
    likes: '10',
    uploaded_at: '2026-01-01T00:00:00Z',
    published_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    imported_at: '2026-01-01T00:00:00Z',
    cover_count: 4,
  }))
}

describe('ComicGrid', () => {
  it('renders skeletons during loading', () => {
    const wrapper = mount(ComicGrid, {
      props: {
        loading: true,
        items: [],
        hasAnyItems: false,
      },
    })

    expect(wrapper.findAll('.skeleton-card').length).toBe(6)
  })

  it('renders empty shelf when not loading and empty', () => {
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: [],
        hasAnyItems: false,
      },
    })

    expect(wrapper.find('.empty-shelf').exists()).toBe(true)
    expect(wrapper.text()).toContain('书架还是空的')
  })

  it('chunks items by batchStep (default 12) for DOM cards and shows sentinel', async () => {
    const comics = makeComics(25)
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: comics,
        hasAnyItems: true,
        batchStep: 12,
      },
    })

    // Initially only 12 items rendered, fold card rendered in grid
    expect(wrapper.findAll('.mock-comic-card').length).toBe(12)
    const foldCard = wrapper.find('.shelf-fold-card')
    expect(foldCard.exists()).toBe(true)
    expect(foldCard.text()).toContain('+13 本')
    expect(wrapper.find('.shelf-sentinel').exists()).toBe(false)

    // Click stepped expand button in fold card to expand next batch
    await foldCard.find('button.btn-primary').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(24)
    expect(wrapper.find('.shelf-fold-card').text()).toContain('+1 本')
    expect(wrapper.find('.shelf-fold-card').text()).toContain('收整书架')

    // Click stepped expand button in fold card again (all 25 items rendered)
    await wrapper.find('.shelf-fold-card button.btn-primary').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(25)
    // Fold card is gone, sentinel appears with collapse action
    expect(wrapper.find('.shelf-fold-card').exists()).toBe(false)
    const sentinel = wrapper.find('.shelf-sentinel')
    expect(sentinel.exists()).toBe(true)
    expect(sentinel.text()).toContain('全架藏书已展开')

    // Click collapse button to fold back
    await sentinel.find('button').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(12)
    expect(wrapper.find('.shelf-fold-card').exists()).toBe(true)

    // Expand once more, then test collapsing directly from the fold card!
    await wrapper.find('.shelf-fold-card button.btn-primary').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(24)
    const cardCollapseBtn = wrapper
      .find('.shelf-fold-card')
      .findAll('button')
      .find((b) => b.text().includes('收整书架'))
    expect(cardCollapseBtn).toBeDefined()
    await cardCollapseBtn!.trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(12)
  })

  it('resets visible items when items prop changes', async () => {
    const comics1 = makeComics(25)
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: comics1,
        hasAnyItems: true,
        batchStep: 12,
      },
    })

    // Click load more in fold card
    await wrapper.find('.shelf-fold-card button.btn-primary').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(24)

    // Items filtered or changed to new list of 20 items
    const comics2 = makeComics(20)
    await wrapper.setProps({ items: comics2 } as Record<string, unknown>)

    // Should reset back to 12
    expect(wrapper.findAll('.mock-comic-card').length).toBe(12)
  })

  it('separates unread comics and completed comics into active shelf and archive drawer in split mode', async () => {
    // 5 unread comics + 15 completed comics
    const unreadComics = makeComics(5).map((c, i) => ({
      ...c,
      source_id: `unread_${i}`,
      title: `未读漫画 ${i + 1}`,
      last_page: 0,
      page_count: 20,
    }))
    const completedComics = makeComics(15).map((c, i) => ({
      ...c,
      source_id: `completed_${i}`,
      title: `已读漫画 ${i + 1}`,
      last_page: 20,
      page_count: 20,
    }))
    const mixed = [...unreadComics, ...completedComics]

    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: mixed,
        hasAnyItems: true,
        batchStep: 12,
        isRecentSort: true,
      },
    })

    // Active shelf should render only the 5 unread comics
    const activeGrid = wrapper.find('.active-shelf-grid')
    expect(activeGrid.exists()).toBe(true)
    expect(activeGrid.findAll('.mock-comic-card').length).toBe(5)
    // 5 <= 12, so no fold card needed in active shelf
    expect(activeGrid.find('.shelf-fold-card').exists()).toBe(false)

    // Archive drawer exists
    const drawer = wrapper.find('.shelf-archive-drawer')
    expect(drawer.exists()).toBe(true)
    expect(drawer.text()).toContain('卷末归档 · 已读完 15 本')
    expect(drawer.classes()).not.toContain('is-open')

    // Click header to open drawer
    await drawer.find('.archive-drawer-header').trigger('click')
    expect(drawer.classes()).toContain('is-open')

    // Inside drawer, initial batch is 12 completed cards + fold card
    const archiveGrid = drawer.find('.archive-shelf-grid')
    expect(archiveGrid.findAll('.mock-comic-card').length).toBe(12)
    const archiveFoldCard = archiveGrid.find('.shelf-fold-card--archive')
    expect(archiveFoldCard.exists()).toBe(true)
    expect(archiveFoldCard.text()).toContain('+3 本已读')

    // Expand next batch in drawer
    await archiveFoldCard.find('button.btn-primary').trigger('click')
    expect(archiveGrid.findAll('.mock-comic-card').length).toBe(15)

    // Archive sentinel is displayed
    const archiveSentinel = drawer.find('.shelf-sentinel')
    expect(archiveSentinel.exists()).toBe(true)
    expect(archiveSentinel.text()).toContain('全归档已展开')

    // Click collapse inside drawer
    await archiveSentinel.find('button').trigger('click')
    expect(archiveGrid.findAll('.mock-comic-card').length).toBe(12)
  })

  it('renders archive divider and flat grid when all comics are completed', () => {
    const completedComics = makeComics(15).map((c, i) => ({
      ...c,
      source_id: `completed_${i}`,
      title: `已读漫画 ${i + 1}`,
      last_page: 20,
      page_count: 20,
    }))

    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: completedComics,
        hasAnyItems: true,
        batchStep: 12,
        isRecentSort: true,
      },
    })

    // No drawer in allCompleted mode
    expect(wrapper.find('.shelf-archive-drawer').exists()).toBe(false)

    // Archive divider banner is displayed
    const divider = wrapper.find('.shelf-archive-divider')
    expect(divider.exists()).toBe(true)
    expect(divider.text()).toContain('典藏归档 · 全部已翻阅（15 本）')

    // Renders single flat grid with chunking
    expect(wrapper.findAll('.mock-comic-card').length).toBe(12)
    const foldCard = wrapper.find('.shelf-fold-card')
    expect(foldCard.exists()).toBe(true)
    expect(foldCard.text()).toContain('+3 本')
  })

  it('renders flat single grid without drawer or divider when isRecentSort is false', () => {
    const unread = makeComics(5).map((c, i) => ({
      ...c,
      source_id: `unread_${i}`,
      last_page: 0,
      page_count: 20,
    }))
    const completed = makeComics(5).map((c, i) => ({
      ...c,
      source_id: `completed_${i}`,
      last_page: 20,
      page_count: 20,
    }))
    const mixed = [...unread, ...completed]

    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: mixed,
        hasAnyItems: true,
        batchStep: 12,
        isRecentSort: false,
      },
    })

    // Neither drawer nor divider rendered in non-recent sort (e.g. title or search)
    expect(wrapper.find('.shelf-archive-drawer').exists()).toBe(false)
    expect(wrapper.find('.shelf-archive-divider').exists()).toBe(false)
    expect(wrapper.findAll('.mock-comic-card').length).toBe(10)
  })

  it('honors initialActiveCount and initialArchiveOpen for shelf state restoration', async () => {
    const unread = makeComics(30).map((c, i) => ({
      ...c,
      source_id: `unread_${i}`,
      last_page: 0,
      page_count: 20,
    }))
    const completed = makeComics(20).map((c, i) => ({
      ...c,
      source_id: `completed_${i}`,
      last_page: 20,
      page_count: 20,
    }))
    const mixed = [...unread, ...completed]

    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: mixed,
        hasAnyItems: true,
        batchStep: 12,
        initialActiveCount: 24,
        initialArchiveOpen: true,
        initialArchiveCount: 15,
      },
    })

    // Active shelf should render 24 items immediately
    const activeGrid = wrapper.find('.active-shelf-grid')
    expect(activeGrid.findAll('.mock-comic-card').length).toBe(24)

    // Archive drawer should be open and render 15 completed items
    const drawer = wrapper.find('.shelf-archive-drawer')
    expect(drawer.exists()).toBe(true)
    const drawerGrid = wrapper.find('.archive-shelf-grid')
    expect(drawerGrid.findAll('.mock-comic-card').length).toBe(15)

    // SWR background update should not wipe out restored counts
    const updatedMixed = [...mixed]
    await wrapper.setProps({ items: updatedMixed } as Record<string, unknown>)
    expect(activeGrid.findAll('.mock-comic-card').length).toBe(24)
    expect(drawerGrid.findAll('.mock-comic-card').length).toBe(15)
  })

  it('triggers safety brake at brakeThreshold and allows continuation in ComicGrid', async () => {
    const comics = makeComics(80)
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: comics,
        hasAnyItems: true,
        batchStep: 20,
        brakeThreshold: 40,
        isRecentSort: false, // Unified grid mode
      },
    })

    // Starts at 20
    expect(wrapper.findAll('.mock-comic-card').length).toBe(20)
    let foldCard = wrapper.find('.shelf-fold-card')
    expect(foldCard.classes()).not.toContain('is-braked')

    // Expand to 40 (hits 40 brakeThreshold)
    await foldCard.find('button.btn-primary').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(40)
    foldCard = wrapper.find('.shelf-fold-card')
    expect(foldCard.classes()).toContain('is-braked')
    expect(foldCard.text()).toContain('流式加载已触发安全刹车')
    expect(foldCard.find('button.btn-primary').text()).toContain('继续向下探索')

    // Click continue exploration
    await foldCard.find('button.btn-primary').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(60)
  })

  it('renders stream loading indicator when loadingMore is true', () => {
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        loadingMore: true,
        items: makeComics(10),
        hasAnyItems: true,
      },
    })

    const loadingBar = wrapper.find('.stream-loading-bar')
    expect(loadingBar.exists()).toBe(true)
    expect(loadingBar.text()).toContain('正在载入后续藏书')
  })

  it('automatically reveals newly appended items when new page arrives after reaching end of previous page', async () => {
    // Page 1 has 24 comics
    const page1 = makeComics(24)
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: page1,
        hasAnyItems: true,
        batchStep: 12,
        isRecentSort: false, // Unified grid mode
        initialUnifiedCount: 24, // User has scrolled to the end of page 1
        hasMore: true,
      },
    })

    // 24 comics currently rendered
    expect(wrapper.findAll('.mock-comic-card').length).toBe(24)

    // Page 2 arrives (24 more items appended, total 48)
    const page2 = makeComics(48)
    await wrapper.setProps({ items: page2 } as Record<string, unknown>)

    // Newly appended page should automatically expand newly arrived batch (total 48)
    expect(wrapper.findAll('.mock-comic-card').length).toBe(48)
  })

  it('automatically reveals newly appended active items in split mode', async () => {
    const page1 = makeComics(24).map((c, i) => ({
      ...c,
      source_id: `unread_${i}`,
      last_page: 0,
    }))
    const completed = makeComics(5).map((c, i) => ({
      ...c,
      source_id: `completed_${i}`,
      last_page: 20,
    }))
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: [...page1, ...completed],
        hasAnyItems: true,
        batchStep: 12,
        isRecentSort: true,
        initialActiveCount: 24,
        hasMore: true,
      },
    })

    const activeGrid = wrapper.find('.active-shelf-grid')
    expect(activeGrid.findAll('.mock-comic-card').length).toBe(24)

    // Page 2 arrives with 24 more unread items
    const page2 = makeComics(24).map((c, i) => ({
      ...c,
      source_id: `unread_p2_${i}`,
      last_page: 0,
    }))
    await wrapper.setProps({ items: [...page1, ...page2, ...completed] } as Record<string, unknown>)

    // Newly appended page should automatically expand active batch (total 48)
    expect(activeGrid.findAll('.mock-comic-card').length).toBe(48)
  })
})

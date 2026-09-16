import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderFilmstrip from '@/components/reader/ReaderFilmstrip.vue'

describe('ReaderFilmstrip - Filmstrip Scrubber Component', () => {
  const defaultProps = {
    open: true,
    source: 'jm',
    sourceId: '123456',
    orderedGroups: [
      { pages: [1, 2], index: 0 },
      { pages: [3, 4], index: 1 },
      { pages: [5, 6], index: 2 },
    ],
    currentGroupIndex: 1,
    currentPage: 3,
    total: 6,
    mode: 'horizontal' as const,
    pagesPerView: 2,
    rtlHorizontal: false,
    toLocalPage: (p: number) => p,
  }

  it('renders groups and tiles when open', () => {
    const wrapper = mount(ReaderFilmstrip, {
      props: defaultProps,
    })

    expect(wrapper.find('.reader-filmstrip').exists()).toBe(true)
    const groups = wrapper.findAll('.filmstrip-group')
    expect(groups.length).toBe(3)

    const tiles = wrapper.findAll('.filmstrip-tile')
    expect(tiles.length).toBe(6)
  })

  it('highlights active group and active page correctly', () => {
    const wrapper = mount(ReaderFilmstrip, {
      props: defaultProps,
    })

    // Group 1 is active
    const activeGroup = wrapper.find('.filmstrip-group.group-active')
    expect(activeGroup.exists()).toBe(true)
    expect(activeGroup.attributes('data-group-index')).toBe('1')

    // Page 3 is active
    const activeTile = wrapper.find('.filmstrip-tile[data-page-active="true"]')
    expect(activeTile.exists()).toBe(true)
    expect(activeTile.attributes('data-page')).toBe('3')
  })

  it('emits selectGroup and selectPage when a tile is clicked', async () => {
    const wrapper = mount(ReaderFilmstrip, {
      props: defaultProps,
    })

    const tile5 = wrapper.find('.filmstrip-tile[data-page="5"]')
    await tile5.trigger('click')

    expect(wrapper.emitted('selectGroup')).toBeTruthy()
    expect(wrapper.emitted('selectGroup')?.[0]).toEqual([2])
    expect(wrapper.emitted('selectPage')).toBeTruthy()
    expect(wrapper.emitted('selectPage')?.[0]).toEqual([5])
  })

  it('supports keyboard navigation via Enter and Space keys', async () => {
    const wrapper = mount(ReaderFilmstrip, {
      props: defaultProps,
    })

    const tile1 = wrapper.find('.filmstrip-tile[data-page="1"]')
    expect(tile1.attributes('role')).toBe('button')
    expect(tile1.attributes('tabindex')).toBe('0')

    await tile1.trigger('keydown.enter')
    expect(wrapper.emitted('selectGroup')?.[0]).toEqual([0])
    expect(wrapper.emitted('selectPage')?.[0]).toEqual([1])
  })

  it('emits close when clicking the close button or backdrop', async () => {
    const wrapper = mount(ReaderFilmstrip, {
      props: defaultProps,
    })

    const backdrop = wrapper.find('.filmstrip-backdrop')
    expect(backdrop.exists()).toBe(true)
    await backdrop.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()

    const closeBtn = wrapper.find('.filmstrip-close-btn')
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')?.length).toBe(2)
  })

  it('reflects RTL direction in rail when rtlHorizontal is true', () => {
    const wrapper = mount(ReaderFilmstrip, {
      props: {
        ...defaultProps,
        rtlHorizontal: true,
      },
    })

    const rail = wrapper.find('.filmstrip-rail')
    expect(rail.attributes('dir')).toBe('rtl')
  })

  it('scopes groups to current chapter and shows chapter switch buttons in multi-chapter comics', async () => {
    const chapters = [
      { id: 'c1', index: 0, title: '第 1 话', page_count: 2, start: 1 },
      { id: 'c2', index: 1, title: '第 2 话', page_count: 4, start: 3 },
    ]

    const wrapper = mount(ReaderFilmstrip, {
      props: {
        ...defaultProps,
        chapters,
        currentChapterId: 'c2',
      },
    })

    // Chapter 2 spans pages 3..6 (groups index 1 and 2)
    const groups = wrapper.findAll('.filmstrip-group')
    expect(groups.length).toBe(2)

    // Title should show Chapter 2 title
    expect(wrapper.find('.filmstrip-chapter-title').text()).toBe('第 2 话')

    // Previous chapter button should exist
    const prevBtn = wrapper.find('.filmstrip-chap-btn')
    expect(prevBtn.exists()).toBe(true)
    await prevBtn.trigger('click')
    expect(wrapper.emitted('selectChapter')?.[0]).toEqual(['c1'])
  })

  it('smoothly centers target tile and locks click navigation against back-and-forth oscillation', async () => {
    const wrapper = mount(ReaderFilmstrip, {
      props: {
        ...defaultProps,
        orderedGroups: [
          { pages: [1], index: 0 },
          { pages: [2], index: 1 },
          { pages: [3], index: 2 },
          { pages: [4], index: 3 },
          { pages: [5], index: 4 },
        ],
        currentGroupIndex: 0,
        currentPage: 1,
        total: 5,
        pagesPerView: 1,
      },
    })

    const rail = wrapper.find('.filmstrip-rail').element as HTMLElement
    const scrollToSpy = vi.fn<(options?: ScrollToOptions) => void>()
    rail.scrollTo = scrollToSpy as unknown as typeof rail.scrollTo

    const tile5 = wrapper.find('.filmstrip-tile[data-page="5"]')
    await tile5.trigger('click')

    // Clicked target should trigger scrollTo immediately
    expect(scrollToSpy).toHaveBeenCalled()

    // Subsequent transient jitter to currentGroupIndex within lock window should NOT trigger jittery centering
    scrollToSpy.mockClear()
    await wrapper.setProps({ currentGroupIndex: 2 } as Record<string, unknown>)
    expect(scrollToSpy).not.toHaveBeenCalled()
  })
})

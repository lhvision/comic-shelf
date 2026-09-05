import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import PageIndexGrid from '@/components/detail/PageIndexGrid.vue'
import type { PageRecord } from '@/types'

// Mock subcomponents
vi.mock('@/components/detail/PageTile.vue', () => ({
  default: {
    name: 'PageTile',
    props: ['source', 'sourceId', 'index', 'cached', 'label', 'chapterId'],
    template: '<div class="mock-page-tile" :data-index="index">{{ label || index }}</div>',
  },
}))

vi.mock('@/components/AppIcon.vue', () => ({
  default: {
    name: 'AppIcon',
    props: ['name', 'size'],
    template: '<span class="mock-icon" :data-name="name" />',
  },
}))

function makePages(count: number): PageRecord[] {
  return Array.from({ length: count }, (_, i) => ({
    index: i + 1,
    file: `${String(i + 1).padStart(5, '0')}.webp`,
    ext: '.webp',
    cached: i < 5,
  }))
}

describe('PageIndexGrid', () => {
  it('renders all page tiles and an independent overflow card when remainingPages > 0', async () => {
    const pages = makePages(24)
    const wrapper = mount(PageIndexGrid, {
      props: {
        source: 'jm',
        sourceId: '123456',
        pages,
        remainingPages: 50,
        pageStep: 24,
        showingRange: '已显示 24 / 74 页',
        canCollapse: false,
      },
    })

    // Renders all 24 page tiles unblocked
    expect(wrapper.findAll('.mock-page-tile').length).toBe(24)

    // Independent overflow card appended to grid
    const overflowTile = wrapper.find('.page-tile-overflow')
    expect(overflowTile.exists()).toBe(true)
    expect(overflowTile.text()).toContain('+50')
    expect(overflowTile.text()).toContain('再展开 24 页')

    // Click overflow tile triggers loadMore emit
    await overflowTile.trigger('click')
    expect(wrapper.emitted('loadMore')).toBeTruthy()
    expect(wrapper.emitted('loadMore')?.length).toBe(1)
  })

  it('provides expand all and collapse controls in the fold bar without button duplication', async () => {
    const pages = makePages(48)
    const wrapper = mount(PageIndexGrid, {
      props: {
        source: 'jm',
        sourceId: '123456',
        pages,
        remainingPages: 26,
        pageStep: 24,
        showingRange: '已显示 48 / 74 页',
        canCollapse: true,
      },
    })

    const foldBar = wrapper.find('.page-fold-bar')
    expect(foldBar.exists()).toBe(true)
    expect(foldBar.text()).toContain('已展现 48 页')
    expect(foldBar.text()).toContain('余 26 页已折叠')

    // Buttons: 1: 展开全部, 2: 收起画卷 (stepped expand is in the overflow tile)
    const buttons = foldBar.findAll('button')
    expect(buttons.length).toBe(2)

    // Click expand all
    await buttons[0]!.trigger('click')
    expect(wrapper.emitted('loadAll')).toBeTruthy()

    // Click collapse
    await buttons[1]!.trigger('click')
    expect(wrapper.emitted('collapse')).toBeTruthy()
  })

  it('hides overflow card and shows fully expanded state when remainingPages is 0', () => {
    const pages = makePages(74)
    const wrapper = mount(PageIndexGrid, {
      props: {
        source: 'jm',
        sourceId: '123456',
        pages,
        remainingPages: 0,
        pageStep: 24,
        showingRange: '已显示 74 / 74 页',
        canCollapse: true,
      },
    })

    // No overflow card
    expect(wrapper.find('.page-tile-overflow').exists()).toBe(false)

    // Fold bar shows fully expanded text and collapse button
    const foldBar = wrapper.find('.page-fold-bar')
    expect(foldBar.exists()).toBe(true)
    expect(foldBar.text()).toContain('全卷画页已展开')
    expect(foldBar.findAll('button').length).toBe(1) // only collapse button
  })
})

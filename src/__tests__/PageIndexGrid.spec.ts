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
  it('renders all page tiles and an independent fold card when remainingPages > 0', async () => {
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

    // Independent fold card appended to grid
    const foldCard = wrapper.find('.page-fold-card')
    expect(foldCard.exists()).toBe(true)
    expect(foldCard.text()).toContain('+50 页已收纳')
    expect(foldCard.text()).toContain('画卷余页已收纳')
    expect(foldCard.text()).toContain('再展开 24 页')
    expect(foldCard.text()).toContain('展开全部')

    // Sentinel bar is hidden while folded to eliminate double controls
    expect(wrapper.find('.page-sentinel').exists()).toBe(false)

    // Click stepped expand button in fold card triggers loadMore emit
    await foldCard.find('button.btn-primary').trigger('click')
    expect(wrapper.emitted('loadMore')).toBeTruthy()
    expect(wrapper.emitted('loadMore')?.length).toBe(1)

    // Click expand all in fold card triggers loadAll emit
    const allBtn = foldCard.findAll('button').find((b) => b.text().includes('展开全部'))
    expect(allBtn).toBeDefined()
    await allBtn!.trigger('click')
    expect(wrapper.emitted('loadAll')).toBeTruthy()
  })

  it('provides collapse control in the fold card when canCollapse is true', async () => {
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

    const foldCard = wrapper.find('.page-fold-card')
    expect(foldCard.exists()).toBe(true)
    expect(wrapper.find('.page-sentinel').exists()).toBe(false)

    // Buttons in card: 1: 再展开 24 页, 2: 展开全部, 3: 收起画卷
    const buttons = foldCard.findAll('button')
    expect(buttons.length).toBe(3)

    // Click collapse
    await buttons[2]!.trigger('click')
    expect(wrapper.emitted('collapse')).toBeTruthy()
  })

  it('hides fold card and shows fully expanded sentinel bar when remainingPages is 0', async () => {
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

    // No fold card in grid
    expect(wrapper.find('.page-fold-card').exists()).toBe(false)

    // Sentinel bar shows fully expanded text and collapse button
    const sentinel = wrapper.find('.page-sentinel')
    expect(sentinel.exists()).toBe(true)
    expect(sentinel.text()).toContain('全卷画页已展开')
    expect(sentinel.findAll('button').length).toBe(1) // only collapse button

    // Click collapse button in sentinel bar
    await sentinel.find('button').trigger('click')
    expect(wrapper.emitted('collapse')).toBeTruthy()
  })
})

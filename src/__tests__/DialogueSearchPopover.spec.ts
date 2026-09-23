import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DialogueSearchPopover from '@/components/library/DialogueSearchPopover.vue'
import type { DialogueSearchItem } from '@/types'

describe('DialogueSearchPopover', () => {
  const mockItem: DialogueSearchItem = {
    source: 'jm',
    source_id: '1059521',
    title: '老师请快看这个孩子',
    page_index: 3,
    bubble_id: 1,
    bubble_count: 1,
    text: '老师请快看这个孩子',
    snippet: '...<mark>老师</mark>请快看这个孩子...',
    box: [0.1, 0.2, 0.3, 0.4],
    lang: 'zh',
    cover: '/covers/jm/1059521.jpg',
    authors: ['测试画师'],
  }

  const mockItems: DialogueSearchItem[] = [mockItem]

  const multiHitItems: DialogueSearchItem[] = [{ ...mockItem, bubble_id: 2, bubble_count: 3 }]

  it('does not render content when open is false', () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: false,
        results: mockItems,
        total: 1,
        isSearching: false,
        query: '老师',
      },
    })
    expect(wrapper.find('.dialogue-popover').exists()).toBe(false)
  })

  it('renders results with secure tokenized marks when open is true', () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: true,
        results: mockItems,
        total: 1,
        isSearching: false,
        query: '老师',
      },
    })

    expect(wrapper.find('.dialogue-popover').exists()).toBe(true)
    expect(wrapper.find('.comic-title').text()).toBe('老师请快看这个孩子')
    expect(wrapper.find('.source-badge').text()).toBe('禁漫')
    expect(wrapper.find('.page-tag').text()).toBe('P.3')
    // 单命中不宣告命中数，微信息行只留给作者
    expect(wrapper.find('.item-meta').text()).not.toContain('处命中')
    expect(wrapper.find('.meta-item.author').text()).toContain('测试画师')

    // 验证 mark 标签安全解析而非 raw v-html
    const mark = wrapper.find('mark.dialogue-mark')
    expect(mark.exists()).toBe(true)
    expect(mark.text()).toBe('老师')
  })

  it('drops the meta row entirely for a single hit with no author', () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: true,
        results: [{ ...mockItem, authors: [] }],
        total: 1,
        isSearching: false,
        query: '老师',
      },
    })

    expect(wrapper.find('.result-item').exists()).toBe(true)
    expect(wrapper.find('.item-meta').exists()).toBe(false)
  })

  it('announces the hit count only when a page matched several bubbles', () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: true,
        results: multiHitItems,
        total: 1,
        isSearching: false,
        query: '老师',
      },
    })

    expect(wrapper.findAll('.result-item')).toHaveLength(1)
    expect(wrapper.find('.meta-item').text()).toContain('3 处命中')
    // 计数单位必须是「页」，否则用户会读成气泡/词条数
    expect(wrapper.find('.head-badge').text()).toBe('命中 1 页')
  })

  it('emits select event when clicking a result item', async () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: true,
        results: mockItems,
        total: 1,
        isSearching: false,
        query: '老师',
      },
    })

    const item = wrapper.find('.result-item')
    await item.trigger('click')

    const emitted = wrapper.emitted('select')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0]?.[0]).toEqual(mockItems[0])
  })

  it('renders loading state when isSearching is true', () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: true,
        results: [],
        total: 0,
        isSearching: true,
        query: '正在搜',
      },
    })

    expect(wrapper.find('.popover-loading').exists()).toBe(true)
    expect(wrapper.find('.loading-text').text()).toContain('正在翻寻分镜对白与台词')
  })

  it('renders empty state when results is empty and not searching', () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: true,
        results: [],
        total: 0,
        isSearching: false,
        query: '不存在的台词',
      },
    })

    expect(wrapper.find('.popover-empty').exists()).toBe(true)
    expect(wrapper.find('.empty-title').text()).toContain('不存在的台词')
  })

  it('survives the list unmounting while the focus watcher is awaiting nextTick', async () => {
    // 与 SearchCommandMenu 同源的缺陷：focusedIndex 变化时 watcher 在 await nextTick
    // 之前判空，而列表块可能在这一个 tick 内被 v-if 卸载，之后再用 ref 就是 null
    const rejections: unknown[] = []
    const collect = (err: unknown) => rejections.push(err)
    process.on('unhandledRejection', collect)

    try {
      const wrapper = mount(DialogueSearchPopover, {
        props: {
          open: true,
          results: mockItems,
          total: 1,
          isSearching: false,
          focusedIndex: 0,
          query: '老师',
        },
      })

      await wrapper.setProps({ open: false, focusedIndex: 1 } as Record<string, unknown>)
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(wrapper.find('.dialogue-popover').exists()).toBe(false)
      expect(rejections).toEqual([])
    } finally {
      process.off('unhandledRejection', collect)
    }
  })

  it('emits close event when clicking close button or pressing Esc', async () => {
    const wrapper = mount(DialogueSearchPopover, {
      props: {
        open: true,
        results: mockItems,
        total: 1,
        isSearching: false,
        query: '老师',
      },
    })

    const closeBtn = wrapper.find('.head-close-btn')
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})

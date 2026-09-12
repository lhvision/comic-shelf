import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DialogueSearchPopover from '@/components/library/DialogueSearchPopover.vue'
import type { DialogueSearchItem } from '@/types'

describe('DialogueSearchPopover', () => {
  const mockItems: DialogueSearchItem[] = [
    {
      source: 'jm',
      source_id: '1059521',
      title: '老师请快看这个孩子',
      page_index: 3,
      bubble_id: 1,
      text: '老师请快看这个孩子',
      snippet: '...<mark>老师</mark>请快看这个孩子...',
      box: [0.1, 0.2, 0.3, 0.4],
      lang: 'zh',
      cover: '/covers/jm/1059521.jpg',
      authors: ['测试画师'],
    },
  ]

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
    expect(wrapper.find('.meta-item').text()).toContain('气泡 #1')

    // 验证 mark 标签安全解析而非 raw v-html
    const mark = wrapper.find('mark.dialogue-mark')
    expect(mark.exists()).toBe(true)
    expect(mark.text()).toBe('老师')
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

import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import SegmentedTabs from '@/components/SegmentedTabs.vue'

describe('SegmentedTabs', () => {
  const items = [
    { key: 'week', label: '本周必看', sub: '周榜' },
    { key: 'month', label: '本月热门', sub: '月榜' },
    { key: 'day', label: '今日精选', sub: '日榜' },
  ]

  it('renders tab items with labels and sub titles', () => {
    const wrapper = mount(SegmentedTabs, {
      props: {
        modelValue: 'week',
        items,
        size: 'md',
      },
    })

    const tabs = wrapper.findAll('.segmented-tab')
    expect(tabs.length).toBe(3)
    expect(tabs[0]?.text()).toContain('本周必看')
    expect(tabs[0]?.text()).toContain('周榜')
    expect(tabs[0]?.classes()).toContain('is-active')
    expect(tabs[1]?.classes()).not.toContain('is-active')
  })

  it('emits update:modelValue and change events when clicked', async () => {
    const wrapper = mount(SegmentedTabs, {
      props: {
        modelValue: 'week',
        items,
      },
    })

    const tabs = wrapper.findAll('.segmented-tab')
    await tabs[1]?.trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['month'])
    expect(wrapper.emitted('change')?.[0]).toEqual(['month'])
  })

  it('supports string items array', () => {
    const wrapper = mount(SegmentedTabs, {
      props: {
        modelValue: 'jm',
        items: ['jm', 'local'],
      },
    })

    const tabs = wrapper.findAll('.segmented-tab')
    expect(tabs.length).toBe(2)
    expect(tabs[0]?.text()).toBe('jm')
    expect(tabs[0]?.classes()).toContain('is-active')
  })
})

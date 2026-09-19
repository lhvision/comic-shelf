import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DiscoveryCard from '@/components/discovery/DiscoveryCard.vue'
import type { DiscoveryItem } from '@/types'

describe('DiscoveryCard on-demand cover viewing (Scheme A)', () => {
  const picaItemWithCover: DiscoveryItem = {
    id: 'picacg_6aa41d3bf7e21a74faf94e42',
    source_id: '6aa41d3bf7e21a74faf94e42',
    source: 'picacg',
    title: '测试哔咔漫画',
    author: '测试画师',
    category: '同人',
    cover_url: 'https://storage-b.picacomic.com/static/sample.jpg',
    url: 'https://picawang.com/comic/6aa41d3bf7e21a74faf94e42',
    in_library: false,
  }

  const jmItemWithoutCover: DiscoveryItem = {
    id: 'jm_123456',
    source_id: '123456',
    source: 'jm',
    title: '测试禁漫漫画',
    author: '禁漫作者',
    category: '单本',
    cover_url: '',
    url: 'https://18comic.vip/album/123456',
    in_library: false,
  }

  it('renders placeholder by default without loading any cover image', () => {
    const wrapper = mount(DiscoveryCard, {
      props: {
        item: picaItemWithCover,
        rank: 1,
      },
    })

    // Default: No img element rendered
    expect(wrapper.find('img.cover-img').exists()).toBe(false)
    // Placeholder is present
    expect(wrapper.find('.cover-placeholder').exists()).toBe(true)
    // "查看封面" trigger button exists because item has cover_url
    const trigger = wrapper.find('.cover-action-trigger')
    expect(trigger.exists()).toBe(true)
    expect(trigger.text()).toContain('查看封面')
  })

  it('toggles cover image on clicking 查看封面 and hides it on 收起封面', async () => {
    const wrapper = mount(DiscoveryCard, {
      props: {
        item: picaItemWithCover,
        rank: 1,
      },
    })

    const trigger = wrapper.find('.cover-action-trigger')
    await trigger.trigger('click')

    // Now cover should be displayed
    const img = wrapper.find('img.cover-img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toContain('/api/discovery/cover?')
    expect(img.attributes('src')).toContain('source=picacg')
    expect(img.attributes('src')).toContain('source_id=6aa41d3bf7e21a74faf94e42')

    // Loading overlay is visible while loading
    expect(wrapper.find('.cover-loading-overlay').exists()).toBe(true)

    // Simulate load event
    await img.trigger('load')
    expect(wrapper.find('.cover-loading-overlay').exists()).toBe(false)
    expect(img.classes()).toContain('is-loaded')

    // "收起封面" button is visible
    const hideBtn = wrapper.find('.cover-toggle-overlay-btn')
    expect(hideBtn.exists()).toBe(true)
    expect(hideBtn.text()).toContain('收起封面')

    // Click "收起封面" to close
    await hideBtn.trigger('click')
    expect(wrapper.find('img.cover-img').exists()).toBe(false)
    expect(wrapper.find('.cover-placeholder').exists()).toBe(true)
  })

  it('does not display 查看封面 button when item has no cover_url', () => {
    const wrapper = mount(DiscoveryCard, {
      props: {
        item: jmItemWithoutCover,
        rank: 5,
      },
    })

    expect(wrapper.find('img.cover-img').exists()).toBe(false)
    expect(wrapper.find('.cover-placeholder').exists()).toBe(true)
    expect(wrapper.find('.cover-action-trigger').exists()).toBe(false)
  })

  it('displays error overlay with retry button when image fails to load', async () => {
    const wrapper = mount(DiscoveryCard, {
      props: {
        item: picaItemWithCover,
        rank: 2,
      },
    })

    await wrapper.find('.cover-action-trigger').trigger('click')
    const img = wrapper.find('img.cover-img')
    expect(img.exists()).toBe(true)

    // Trigger image load error
    await img.trigger('error')

    expect(wrapper.find('.cover-error-overlay').exists()).toBe(true)
    expect(wrapper.find('.cover-error-overlay').text()).toContain('封面加载失败')
    const retryBtn = wrapper.find('.cover-retry-btn')
    expect(retryBtn.exists()).toBe(true)

    // Click retry
    await retryBtn.trigger('click')
    expect(wrapper.find('.cover-loading-overlay').exists()).toBe(true)
    expect(wrapper.find('.cover-error-overlay').exists()).toBe(false)
  })
})

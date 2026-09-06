import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ComicPageImage from '@/components/ComicPageImage.vue'

describe('ComicPageImage.vue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders initial loading state', () => {
    const wrapper = mount(ComicPageImage, {
      props: {
        src: '/api/library/jm/123/pages/1/file',
        alt: '第 1 页',
      },
    })
    expect(wrapper.attributes('data-state')).toBe('loading')
    expect(wrapper.find('.page-loading-wrapper').exists()).toBe(true)
    expect(wrapper.find('.page-error').exists()).toBe(false)
  })

  it('emits ready and updates state on image load', async () => {
    const wrapper = mount(ComicPageImage, {
      props: {
        src: '/api/library/jm/123/pages/1/file',
        alt: '第 1 页',
      },
    })
    const img = wrapper.find('img')
    await img.trigger('load')

    expect(wrapper.attributes('data-state')).toBe('ready')
    expect(wrapper.find('.page-loading-wrapper').exists()).toBe(false)
    expect(wrapper.emitted('ready')).toBeTruthy()
  })

  it('enters silent auto-retry on error without displaying premature error card', async () => {
    const wrapper = mount(ComicPageImage, {
      props: {
        src: '/api/library/jm/123/pages/1/file',
        alt: '第 1 页',
      },
    })
    const img = wrapper.find('img')
    await img.trigger('error')

    // First error: should remain in loading state (silent retry)
    expect(wrapper.attributes('data-state')).toBe('loading')
    expect(wrapper.find('.page-error').exists()).toBe(false)

    // Advance 1.2s: first retry triggered
    vi.advanceTimersByTime(1200)
    await wrapper.vm.$nextTick()

    const updatedImg = wrapper.find('img')
    expect(updatedImg.attributes('src')).toContain('retry=1')
    expect(updatedImg.attributes('loading')).toBe('eager')
    expect(updatedImg.attributes('fetchpriority')).toBe('high')
  })

  it('displays error card after exhausting 3 auto-retries, and supports manual retry', async () => {
    const wrapper = mount(ComicPageImage, {
      props: {
        src: '/api/library/jm/123/pages/1/file',
        alt: '第 1 页',
      },
    })

    // Attempt 1 -> error -> wait 1.2s -> retry 1
    await wrapper.find('img').trigger('error')
    vi.advanceTimersByTime(1200)
    await wrapper.vm.$nextTick()

    // Attempt 2 -> error -> wait 2.4s -> retry 2
    await wrapper.find('img').trigger('error')
    vi.advanceTimersByTime(2400)
    await wrapper.vm.$nextTick()

    // Attempt 3 -> error -> wait 3.6s -> retry 3
    await wrapper.find('img').trigger('error')
    vi.advanceTimersByTime(3600)
    await wrapper.vm.$nextTick()

    // Attempt 4 (exhausted maxAutoRetries = 3) -> finally show error card
    await wrapper.find('img').trigger('error')
    await wrapper.vm.$nextTick()

    expect(wrapper.attributes('data-state')).toBe('error')
    expect(wrapper.find('.page-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('图片加载失败')

    // Click retry button: resets and starts retry again
    await wrapper.find('.page-error button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.attributes('data-state')).toBe('loading')
    expect(wrapper.find('.page-error').exists()).toBe(false)
  })
})

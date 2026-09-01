import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import CacheProgress from '@/components/CacheProgress.vue'

describe('CacheProgress component', () => {
  it('renders progressbar with accessible name and correct aria values', () => {
    const wrapper = mount(CacheProgress, {
      props: {
        cached: 50,
        total: 100,
      },
    })

    const track = wrapper.find('[role="progressbar"]')
    expect(track.exists()).toBe(true)
    expect(track.attributes('aria-label')).toBe('本地 50%')
    expect(track.attributes('aria-valuemin')).toBe('0')
    expect(track.attributes('aria-valuemax')).toBe('100')
    expect(track.attributes('aria-valuenow')).toBe('50')
    expect(track.attributes('aria-valuetext')).toBe('本地 50%')
  })

  it('renders running state with accessible label and breathing dot', () => {
    const wrapper = mount(CacheProgress, {
      props: {
        cached: 30,
        total: 100,
        running: true,
      },
    })

    const track = wrapper.find('[role="progressbar"]')
    expect(track.attributes('aria-label')).toBe('缓存中 30%')
    expect(wrapper.find('.cache-progress__dot').exists()).toBe(true)
    expect(wrapper.classes()).toContain('is-running')
  })

  it('renders 100% complete state correctly', () => {
    const wrapper = mount(CacheProgress, {
      props: {
        cached: 100,
        total: 100,
      },
    })

    const track = wrapper.find('[role="progressbar"]')
    expect(track.attributes('aria-label')).toBe('本地 100%')
    expect(wrapper.classes()).toContain('is-complete')
  })

  it('clamps negative or out-of-bound cached values within 0% to 100%', () => {
    const negativeWrapper = mount(CacheProgress, {
      props: {
        cached: -10,
        total: 100,
      },
    })
    const negativeTrack = negativeWrapper.find('[role="progressbar"]')
    expect(negativeTrack.attributes('aria-valuenow')).toBe('0')
    expect(negativeTrack.attributes('aria-label')).toBe('本地 0%')

    const overflowWrapper = mount(CacheProgress, {
      props: {
        cached: 150,
        total: 100,
      },
    })
    const overflowTrack = overflowWrapper.find('[role="progressbar"]')
    expect(overflowTrack.attributes('aria-valuenow')).toBe('100')
    expect(overflowTrack.attributes('aria-label')).toBe('本地 100%')
  })
})

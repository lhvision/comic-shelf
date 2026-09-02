import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AppProgressBar from '@/components/AppProgressBar.vue'

describe('AppProgressBar.vue', () => {
  it('renders default progress bar with role and aria attributes', () => {
    const wrapper = mount(AppProgressBar, {
      props: {
        value: 50,
        max: 100,
        label: '加载进度',
      },
    })

    expect(wrapper.attributes('role')).toBe('progressbar')
    expect(wrapper.attributes('aria-valuenow')).toBe('50')
    expect(wrapper.attributes('aria-valuemin')).toBe('0')
    expect(wrapper.attributes('aria-valuemax')).toBe('100')
    expect(wrapper.attributes('aria-label')).toBe('加载进度')
    expect(wrapper.attributes('aria-valuetext')).toBe('50%')
    expect(wrapper.classes()).toContain('app-progress-bar--track')
    expect(wrapper.classes()).toContain('app-progress-bar--accent')
    expect(wrapper.attributes('style')).toContain('--progress: 0.5')
    expect(wrapper.attributes('style')).toContain('--percent: 50%')

    const fill = wrapper.find<HTMLElement>('.app-progress-bar__fill')
    expect(fill.exists()).toBe(true)
  })

  it('supports 0~1 progress prop directly', () => {
    const wrapper = mount(AppProgressBar, {
      props: {
        progress: 0.75,
      },
    })

    expect(wrapper.attributes('aria-valuenow')).toBe('75')
    expect(wrapper.attributes('style')).toContain('--progress: 0.75')
    expect(wrapper.attributes('style')).toContain('--value: 75')
  })

  it('clamps out-of-bounds negative and overflow values', () => {
    const negative = mount(AppProgressBar, {
      props: {
        value: -20,
        max: 100,
      },
    })
    expect(negative.attributes('aria-valuenow')).toBe('0')
    expect(negative.attributes('style')).toContain('--progress: 0')

    const overflow = mount(AppProgressBar, {
      props: {
        value: 120,
        max: 100,
      },
    })
    expect(overflow.attributes('aria-valuenow')).toBe('100')
    expect(overflow.attributes('style')).toContain('--progress: 1')
  })

  it('renders variant and color classes correctly', () => {
    const wrapper = mount(AppProgressBar, {
      props: {
        value: 100,
        variant: 'gauge',
        color: 'success',
        animated: true,
      },
    })

    expect(wrapper.classes()).toContain('app-progress-bar--gauge')
    expect(wrapper.classes()).toContain('app-progress-bar--success')
    expect(wrapper.classes()).toContain('is-animated')
  })

  it('handles invert mode for RTL progression', () => {
    const wrapper = mount(AppProgressBar, {
      props: {
        progress: 0.4,
        invert: true,
      },
    })

    expect(wrapper.classes()).toContain('is-rtl')
    expect(wrapper.attributes('style')).toContain('--progress: 0.4')
  })

  it('handles indeterminate mode correctly without aria-valuenow', () => {
    const wrapper = mount(AppProgressBar, {
      props: {
        indeterminate: true,
        label: '正在处理…',
      },
    })

    expect(wrapper.classes()).toContain('is-indeterminate')
    expect(wrapper.attributes('aria-valuenow')).toBeUndefined()
    expect(wrapper.attributes('aria-valuetext')).toBe('正在加载…')
  })

  it('safely handles NaN and zero max without throwing or breaking CSS variables', () => {
    const wrapper = mount(AppProgressBar, {
      props: {
        value: Number.NaN,
        max: 0,
        progress: Number.NaN,
      },
    })

    expect(wrapper.attributes('aria-valuenow')).toBe('0')
    expect(wrapper.attributes('style')).toContain('--progress: 0')
  })
})

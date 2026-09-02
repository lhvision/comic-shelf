import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderProgress from '@/components/reader/ReaderProgress.vue'

describe('ReaderProgress.vue', () => {
  it('renders progressbar role and accessibility attributes in LTR mode', () => {
    const wrapper = mount(ReaderProgress, {
      props: {
        progress: 0.42,
        invert: false,
      },
    })

    expect(wrapper.attributes('role')).toBe('progressbar')
    expect(wrapper.attributes('aria-valuenow')).toBe('42')
    expect(wrapper.attributes('aria-valuemin')).toBe('0')
    expect(wrapper.attributes('aria-valuemax')).toBe('100')
    expect(wrapper.attributes('aria-label')).toBe('阅读进度')
    expect(wrapper.classes()).not.toContain('is-rtl')
    expect(wrapper.attributes('style')).toContain('--progress: 0.42')

    const fill = wrapper.find('.app-progress-bar__fill')
    expect(fill.exists()).toBe(true)
  })

  it('renders .is-rtl and anchors transformOrigin in RTL mode', () => {
    const wrapper = mount(ReaderProgress, {
      props: {
        progress: 0.85,
        invert: true,
      },
    })

    expect(wrapper.classes()).toContain('is-rtl')
    expect(wrapper.attributes('aria-valuenow')).toBe('85')
    expect(wrapper.attributes('style')).toContain('--progress: 0.85')
  })

  it('updates progress and style reactively when progress prop changes', async () => {
    const wrapper = mount(ReaderProgress, {
      props: {
        progress: 0.1,
      },
    })

    expect(wrapper.attributes('aria-valuenow')).toBe('10')
    expect(wrapper.attributes('style')).toContain('--progress: 0.1')

    await wrapper.setProps({ progress: 0.99 } as Record<string, unknown>)
    expect(wrapper.attributes('style')).toContain('--progress: 0.99')
    expect(wrapper.attributes('aria-valuenow')).toBe('99')
  })
})

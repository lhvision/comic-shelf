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

    const span = wrapper.find('span')
    expect(span.exists()).toBe(true)
    expect(span.element.style.transform).toBe('scaleX(0.42)')
    expect(span.element.style.transformOrigin).toBe('0 50%')
  })

  it('renders .is-rtl and anchors transformOrigin to 100% 50% in RTL mode', () => {
    const wrapper = mount(ReaderProgress, {
      props: {
        progress: 0.85,
        invert: true,
      },
    })

    expect(wrapper.classes()).toContain('is-rtl')
    expect(wrapper.attributes('aria-valuenow')).toBe('85')

    const span = wrapper.find('span')
    expect(span.element.style.transform).toBe('scaleX(0.85)')
    expect(span.element.style.transformOrigin).toBe('100% 50%')
  })

  it('updates transform reactively when progress prop changes', async () => {
    const wrapper = mount(ReaderProgress, {
      props: {
        progress: 0.1,
      },
    })

    const span = wrapper.find('span')
    expect(span.element.style.transform).toBe('scaleX(0.1)')

    await wrapper.setProps({ progress: 0.99 } as Record<string, unknown>)
    expect(span.element.style.transform).toBe('scaleX(0.99)')
    expect(wrapper.attributes('aria-valuenow')).toBe('99')
  })
})

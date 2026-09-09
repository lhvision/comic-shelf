import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderFloatingPill from '@/components/reader/ReaderFloatingPill.vue'

describe('ReaderFloatingPill component', () => {
  it('renders padded page numbers correctly', () => {
    const wrapper = mount(ReaderFloatingPill, {
      props: {
        current: 21,
        total: 45,
        active: true,
        suppressed: false,
      },
    })

    expect(wrapper.text()).toContain('021')
    expect(wrapper.text()).toContain('045')
    expect(wrapper.find('.pill-number.current').text()).toBe('021')
    expect(wrapper.find('.pill-number.total').text()).toBe('045')
    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.attributes('aria-label')).toBe('当前阅读进度：第 21 页，共 45 页')
  })

  it('controls visibility via active and suppressed props', async () => {
    const wrapper = mount(ReaderFloatingPill, {
      props: {
        current: 5,
        total: 30,
        active: true,
        suppressed: false,
      },
    })

    expect(wrapper.attributes('data-visible')).toBe('true')
    expect(wrapper.attributes('aria-hidden')).toBe('false')

    // 当全局 HUD 唤起导致 suppressed = true 时，应强制隐藏
    await wrapper.setProps({ suppressed: true } as Record<string, unknown>)
    expect(wrapper.attributes('data-visible')).toBe('false')
    expect(wrapper.attributes('aria-hidden')).toBe('true')

    // 当停止滚动导致 active = false 时，应平滑隐退
    await wrapper.setProps({ suppressed: false, active: false } as Record<string, unknown>)
    expect(wrapper.attributes('data-visible')).toBe('false')
    expect(wrapper.attributes('aria-hidden')).toBe('true')
  })
})

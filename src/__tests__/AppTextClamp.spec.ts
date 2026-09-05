import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AppTextClamp from '@/components/AppTextClamp.vue'

describe('AppTextClamp', () => {
  it('renders customized HTML tag with line clamp classes', () => {
    const wrapper = mount(AppTextClamp, {
      props: {
        text: '测试超长标题内容',
        as: 'h2',
        lines: 2,
        mono: true,
      },
    })

    const heading = wrapper.find('h2.app-text-clamp')
    expect(heading.exists()).toBe(true)
    expect(heading.classes()).toContain('line-clamp-2')
    expect(heading.classes()).toContain('is-mono')
    expect(heading.text()).toBe('测试超长标题内容')
  })

  it('keeps tooltip disabled when element has no overflow', async () => {
    const wrapper = mount(AppTextClamp, {
      props: {
        text: '短文本',
        lines: 1,
      },
    })

    const clampEl = wrapper.find('.app-text-clamp')
    // 模拟无溢出尺寸
    Object.defineProperty(clampEl.element, 'scrollHeight', { value: 20, configurable: true })
    Object.defineProperty(clampEl.element, 'clientHeight', { value: 20, configurable: true })
    Object.defineProperty(clampEl.element, 'scrollWidth', { value: 60, configurable: true })
    Object.defineProperty(clampEl.element, 'clientWidth', { value: 100, configurable: true })

    await clampEl.trigger('pointerenter')
    await wrapper.vm.$nextTick()

    expect(clampEl.classes()).not.toContain('is-truncated')
    // Tooltip tip 元素在 lazy 且 disabled 状态下不挂载
    const tip = wrapper.find('.tooltip__tip')
    expect(tip.exists()).toBe(false)
  })

  it('activates truncated state and lazy mounts tooltip when overflow is detected on pointerenter', async () => {
    vi.useFakeTimers()
    const wrapper = mount(AppTextClamp, {
      props: {
        text: '非常非常长的多作者或者角色列表超长文本内容',
        lines: 1,
        tooltipWidth: '26rem',
      },
    })

    const clampEl = wrapper.find('.app-text-clamp')
    // 模拟宽度溢出
    Object.defineProperty(clampEl.element, 'scrollHeight', { value: 20, configurable: true })
    Object.defineProperty(clampEl.element, 'clientHeight', { value: 20, configurable: true })
    Object.defineProperty(clampEl.element, 'scrollWidth', { value: 350, configurable: true })
    Object.defineProperty(clampEl.element, 'clientWidth', { value: 150, configurable: true })

    await clampEl.trigger('pointerenter')
    await wrapper.vm.$nextTick()

    expect(clampEl.classes()).toContain('is-truncated')

    // 触发 tooltip-wrapper 的 mouseenter
    await wrapper.find('.tooltip-wrapper').trigger('mouseenter')
    vi.advanceTimersByTime(150)
    await wrapper.vm.$nextTick()

    const tip = wrapper.find('.tooltip__tip')
    expect(tip.exists()).toBe(true)
    expect(tip.text()).toBe('非常非常长的多作者或者角色列表超长文本内容')

    vi.useRealTimers()
  })

  it('respects disabled prop and suppresses tooltip', async () => {
    const wrapper = mount(AppTextClamp, {
      props: {
        text: '强制禁用提示的超长文本',
        lines: 1,
        disabled: true,
      },
    })

    const clampEl = wrapper.find('.app-text-clamp')
    Object.defineProperty(clampEl.element, 'scrollWidth', { value: 300, configurable: true })
    Object.defineProperty(clampEl.element, 'clientWidth', { value: 100, configurable: true })

    await clampEl.trigger('pointerenter')
    await wrapper.vm.$nextTick()

    expect(clampEl.classes()).not.toContain('is-truncated')
    expect(wrapper.find('.tooltip__tip').exists()).toBe(false)
  })

  it('does not access scrollHeight or clientHeight during initial mount (zero forced reflow)', () => {
    const spy = vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(50)
    try {
      mount(AppTextClamp, {
        props: {
          text: '这是一段很长的文本',
          lines: 1,
        },
      })
      expect(spy).not.toHaveBeenCalled()
    } finally {
      spy.mockRestore()
    }
  })

  it('activates tooltip when delay is 0', async () => {
    vi.useFakeTimers()
    const wrapper = mount(AppTextClamp, {
      props: {
        text: '零延迟超长文本提示内容',
        lines: 1,
        delay: 0,
      },
    })

    const clampEl = wrapper.find('.app-text-clamp')
    Object.defineProperty(clampEl.element, 'scrollWidth', { value: 300, configurable: true })
    Object.defineProperty(clampEl.element, 'clientWidth', { value: 100, configurable: true })

    await clampEl.trigger('pointerenter')
    await wrapper.find('.tooltip-wrapper').trigger('mouseenter')
    vi.advanceTimersByTime(0)
    await wrapper.vm.$nextTick()

    const tip = wrapper.find('.tooltip__tip')
    expect(tip.exists()).toBe(true)
    expect(tip.text()).toBe('零延迟超长文本提示内容')

    vi.useRealTimers()
  })

  it('triggers tooltip on touchstart on mobile devices', async () => {
    vi.useFakeTimers()
    const wrapper = mount(AppTextClamp, {
      props: {
        text: '移动端触碰测试文本内容',
        lines: 1,
        delay: 50,
      },
    })

    const clampEl = wrapper.find('.app-text-clamp')
    Object.defineProperty(clampEl.element, 'scrollWidth', { value: 300, configurable: true })
    Object.defineProperty(clampEl.element, 'clientWidth', { value: 100, configurable: true })

    await clampEl.trigger('touchstart')
    vi.advanceTimersByTime(50)
    await wrapper.vm.$nextTick()

    const tip = wrapper.find('.tooltip__tip')
    expect(tip.exists()).toBe(true)
    expect(tip.text()).toBe('移动端触碰测试文本内容')

    vi.useRealTimers()
  })
})

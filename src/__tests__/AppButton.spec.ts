import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AppButton from '@/components/AppButton.vue'

describe('AppButton', () => {
  it('renders default secondary medium button', () => {
    const wrapper = mount(AppButton, {
      slots: {
        default: '点击确认',
      },
    })

    expect(wrapper.text()).toBe('点击确认')
    expect(wrapper.classes()).toContain('btn')
    expect(wrapper.classes()).toContain('btn-secondary')
    expect(wrapper.classes()).toContain('btn-md')
    expect(wrapper.element.tagName.toLowerCase()).toBe('button')
  })

  it('renders with custom variant and size including success', () => {
    const wrapper = mount(AppButton, {
      props: {
        variant: 'success',
        size: 'sm',
      },
      slots: {
        default: '已在书架',
      },
    })

    expect(wrapper.classes()).toContain('btn')
    expect(wrapper.classes()).toContain('btn-success')
    expect(wrapper.classes()).toContain('btn-sm')
  })

  it('renders loading spinner and disables button when loading is true', () => {
    const wrapper = mount(AppButton, {
      props: {
        loading: true,
      },
      slots: {
        default: '保存中',
      },
    })

    expect(wrapper.find('.btn-spinner').exists()).toBe(true)
    expect((wrapper.element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.attributes('aria-busy')).toBe('true')
  })

  it('emits click event when clicked', async () => {
    const wrapper = mount(AppButton, {
      slots: {
        default: '触发',
      },
    })

    await wrapper.trigger('click')
    expect(wrapper.emitted('click')?.length).toBe(1)
  })

  it('does not emit click when disabled', async () => {
    const wrapper = mount(AppButton, {
      props: {
        disabled: true,
      },
      slots: {
        default: '不可用',
      },
    })

    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('supports polymorphic rendering as a link when href is passed', async () => {
    const wrapper = mount(AppButton, {
      props: {
        href: 'https://example.com',
        target: '_blank',
      },
      slots: {
        default: '外部链接',
      },
    })

    expect(wrapper.element.tagName.toLowerCase()).toBe('a')
    expect(wrapper.attributes('href')).toBe('https://example.com')
    expect(wrapper.attributes('target')).toBe('_blank')
    expect(wrapper.attributes('rel')).toBe('noopener noreferrer')
    // 保持原生链接无障碍语义，禁止强覆写 role="button" 导致屏幕阅读器误报及 Space 键失效
    expect(wrapper.attributes('role')).toBeUndefined()

    await wrapper.trigger('click')
    expect(wrapper.emitted('click')?.length).toBe(1)
  })

  it('intercepts clicks on polymorphic link when disabled or loading', async () => {
    const wrapper = mount(AppButton, {
      props: {
        href: 'https://example.com',
        disabled: true,
      },
      slots: {
        default: '不可用链接',
      },
    })

    expect(wrapper.element.tagName.toLowerCase()).toBe('a')
    expect(wrapper.attributes('href')).toBeUndefined()
    expect(wrapper.attributes('aria-disabled')).toBe('true')
    expect(wrapper.attributes('tabindex')).toBe('-1')
    expect(wrapper.classes()).toContain('is-disabled')

    const event = new MouseEvent('click', { bubbles: true, cancelable: true })
    const preventSpy = vi.spyOn(event, 'preventDefault')
    wrapper.element.dispatchEvent(event)

    expect(preventSpy).toHaveBeenCalled()
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('supports RouterLink polymorphism when to prop is provided', () => {
    const wrapper = mount(AppButton, {
      props: {
        to: '/comic/jm/123456',
        variant: 'primary',
      },
      slots: {
        default: '查看详情',
      },
      global: {
        stubs: {
          RouterLink: {
            template: '<a :to="to"><slot /></a>',
            props: ['to'],
          },
        },
      },
    })

    expect(wrapper.classes()).toContain('btn-primary')
    expect(wrapper.attributes('to')).toBe('/comic/jm/123456')
    expect(wrapper.text()).toBe('查看详情')
  })

  it('supports icon-only button mode with shape circle and square', () => {
    const circleBtn = mount(AppButton, {
      props: {
        shape: 'circle',
        icon: 'arrow-left',
        size: 'sm',
      },
      attrs: {
        'aria-label': '返回上一页',
      },
    })

    expect(circleBtn.classes()).toContain('btn-shape-circle')
    expect(circleBtn.classes()).toContain('is-icon-only')
    expect(circleBtn.classes()).toContain('btn-sm')
    expect(circleBtn.findComponent({ name: 'AppIcon' }).exists()).toBe(true)

    const squareBtn = mount(AppButton, {
      props: {
        shape: 'square',
        icon: 'refresh',
      },
      attrs: {
        'aria-label': '刷新',
      },
    })

    expect(squareBtn.classes()).toContain('btn-shape-square')
    expect(squareBtn.classes()).toContain('is-icon-only')
  })

  it('renders prefix icon alongside text when both icon and text are provided', () => {
    const wrapper = mount(AppButton, {
      props: {
        icon: 'book-open',
        variant: 'ghost',
      },
      slots: {
        default: '展开全部',
      },
    })

    expect(wrapper.classes()).not.toContain('is-icon-only')
    expect(wrapper.find('.btn-prefix').exists()).toBe(true)
    expect(wrapper.find('.btn-content').text()).toBe('展开全部')
  })

  it('supports reader dark room theme', () => {
    const wrapper = mount(AppButton, {
      props: {
        theme: 'reader',
        variant: 'ghost',
      },
      slots: {
        default: '暗室按钮',
      },
    })

    expect(wrapper.classes()).toContain('is-reader')
    expect(wrapper.classes()).toContain('btn-ghost')
  })

  it('renders suffix icon when iconPosition is right', () => {
    const wrapper = mount(AppButton, {
      props: {
        icon: 'arrow-right',
        iconPosition: 'right',
      },
      slots: {
        default: '下一话',
      },
    })

    expect(wrapper.find('.btn-prefix').exists()).toBe(false)
    expect(wrapper.find('.btn-suffix').exists()).toBe(true)
    expect(wrapper.find('.btn-content').text()).toBe('下一话')
  })

  it('renders both icon and text slot without suppression when shape is specified with text', () => {
    const wrapper = mount(AppButton, {
      props: {
        shape: 'square',
        icon: 'plus',
      },
      slots: {
        default: '新增话',
      },
    })

    expect(wrapper.classes()).toContain('btn-shape-square')
    expect(wrapper.classes()).not.toContain('is-icon-only')
    expect(wrapper.find('.btn-prefix').exists()).toBe(true)
    expect(wrapper.find('.btn-content').text()).toBe('新增话')
  })
})

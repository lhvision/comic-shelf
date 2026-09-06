import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AppChip from '@/components/AppChip.vue'

describe('AppChip', () => {
  it('renders as semantic span by default for read-only display', () => {
    const wrapper = mount(AppChip, {
      slots: {
        default: '全彩',
      },
    })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.classes()).toContain('chip')
    expect(wrapper.classes()).not.toContain('chip-button')
    expect(wrapper.text()).toBe('全彩')
  })

  it('renders as button when interactive is true', () => {
    const wrapper = mount(AppChip, {
      props: {
        interactive: true,
      },
      slots: {
        default: '全部',
      },
    })

    expect(wrapper.element.tagName).toBe('BUTTON')
    expect(wrapper.attributes('type')).toBe('button')
    expect(wrapper.classes()).toContain('chip')
    expect(wrapper.classes()).toContain('chip-button')
  })

  it('automatically promotes to button and binds aria-pressed when pressed is provided', async () => {
    const wrapper = mount(AppChip, {
      props: {
        pressed: false,
      },
      slots: {
        default: '只看喜欢',
      },
    })

    expect(wrapper.element.tagName).toBe('BUTTON')
    expect(wrapper.classes()).toContain('chip-button')
    expect(wrapper.attributes('aria-pressed')).toBe('false')

    await wrapper.setProps({ pressed: true } as Record<string, unknown>)
    expect(wrapper.attributes('aria-pressed')).toBe('true')
  })

  it('automatically detects @click listener and renders as button', async () => {
    const onClick = vi.fn<(event?: MouseEvent) => void>()
    const wrapper = mount(AppChip, {
      attrs: {
        onClick,
      },
      slots: {
        default: '点击筛选',
      },
    })

    expect(wrapper.element.tagName).toBe('BUTTON')
    expect(wrapper.classes()).toContain('chip-button')

    await wrapper.trigger('click')
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('allows interactive: false to force span rendering', () => {
    const wrapper = mount(AppChip, {
      props: {
        interactive: false,
        pressed: true,
      },
      slots: {
        default: '强制静态',
      },
    })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.classes()).not.toContain('chip-button')
    expect(wrapper.attributes('aria-pressed')).toBeUndefined()
  })

  it('renders count badge correctly via prop', () => {
    const wrapper = mount(AppChip, {
      props: {
        count: 14,
      },
      slots: {
        default: '同人志',
      },
    })

    const countEl = wrapper.find('.tag-count')
    expect(countEl.exists()).toBe(true)
    expect(countEl.text()).toBe('14')
    expect(wrapper.text()).toContain('同人志')
  })

  it('renders custom count slot when provided', () => {
    const wrapper = mount(AppChip, {
      slots: {
        default: '同人志',
        count: '<span class="custom-badge">HOT</span>',
      },
    })

    expect(wrapper.find('.custom-badge').text()).toBe('HOT')
  })

  it('renders prefix icon via icon prop or prefix slot', () => {
    const wrapperWithProp = mount(AppChip, {
      props: {
        icon: 'heart',
      },
      slots: {
        default: '心仪',
      },
    })
    expect(wrapperWithProp.find('.chip-prefix').exists()).toBe(true)

    const wrapperWithSlot = mount(AppChip, {
      slots: {
        prefix: '<span class="test-prefix">★</span>',
        default: '收藏',
      },
    })
    expect(wrapperWithSlot.find('.test-prefix').text()).toBe('★')
  })

  it('renders suffix slot when provided', () => {
    const wrapper = mount(AppChip, {
      slots: {
        default: '更多',
        suffix: '<span class="chevron-arrow">▾</span>',
      },
    })
    expect(wrapper.find('.chip-suffix').text()).toBe('▾')
  })

  it('supports removable mode with close button and emits remove event', async () => {
    const onRemove = vi.fn<(event?: MouseEvent) => void>()
    const wrapper = mount(AppChip, {
      props: {
        removable: true,
        removeAriaLabel: '删除该标签',
      },
      attrs: {
        onRemove,
      },
      slots: {
        default: '可删除标签',
      },
    })

    const delBtn = wrapper.find('.chip-del-btn')
    expect(delBtn.exists()).toBe(true)
    expect(delBtn.attributes('aria-label')).toBe('删除该标签')

    await delBtn.trigger('click')
    expect(wrapper.emitted('remove')).toBeTruthy()
    expect(wrapper.emitted('remove')?.length).toBe(1)
    expect(onRemove).toHaveBeenCalledTimes(1)
  })

  it('applies size and tone variants correctly', () => {
    const wrapper = mount(AppChip, {
      props: {
        size: 'sm',
        tone: 'accent',
      },
      slots: {
        default: '朱砂标签',
      },
    })

    expect(wrapper.classes()).toContain('chip--sm')
    expect(wrapper.attributes('data-tone')).toBe('accent')
  })

  it('disables interactions and prevents click when disabled is true', async () => {
    const onClick = vi.fn<(event?: MouseEvent) => void>()
    const wrapper = mount(AppChip, {
      props: {
        interactive: true,
        disabled: true,
      },
      attrs: {
        onClick,
      },
      slots: {
        default: '禁用胶囊',
      },
    })

    expect(wrapper.classes()).toContain('is-disabled')
    expect(wrapper.attributes('disabled')).toBeDefined()

    await wrapper.trigger('click')
    expect(onClick).not.toHaveBeenCalled()
  })

  it('enforces span root when removable is true to prevent illegal button-in-button HTML nesting', () => {
    const wrapper = mount(AppChip, {
      props: {
        removable: true,
        interactive: true,
      },
      slots: {
        default: '不可嵌套按钮',
      },
    })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.classes()).toContain('chip--removable')
    expect(wrapper.find('button.chip-del-btn').exists()).toBe(true)
  })

  it('supports keyboard enter/space on non-button chip with click listener', async () => {
    const onClick = vi.fn<() => void>()
    const wrapper = mount(AppChip, {
      props: {
        removable: true,
      },
      attrs: {
        onClick,
      },
      slots: {
        default: '键盘无障碍标签',
      },
    })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.attributes('role')).toBe('button')
    expect(wrapper.attributes('tabindex')).toBe('0')

    await wrapper.trigger('keydown.enter')
    expect(onClick).toHaveBeenCalledTimes(1)

    await wrapper.trigger('keydown.space')
    expect(onClick).toHaveBeenCalledTimes(2)
  })
})

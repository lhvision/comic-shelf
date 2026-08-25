import { describe, it, expect } from 'vite-plus/test'
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
  })

  it('renders with custom variant and size', () => {
    const wrapper = mount(AppButton, {
      props: {
        variant: 'primary',
        size: 'sm',
      },
      slots: {
        default: '立即收录',
      },
    })

    expect(wrapper.classes()).toContain('btn')
    expect(wrapper.classes()).toContain('btn-primary')
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
})

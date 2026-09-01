import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import Modal from '@/components/Modal.vue'

describe('Modal Component', () => {
  it('renders default paper theme and size-md correctly', () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '测试纸间弹窗',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    const panel = wrapper.find('.modal-panel')
    expect(panel.exists()).toBe(true)
    expect(panel.classes()).toContain('is-paper')
    expect(panel.classes()).toContain('size-md')
    expect(wrapper.find('.ambient-watermark').exists()).toBe(true)
    expect(wrapper.find('.modal-head h2').text()).toBe('测试纸间弹窗')
  })

  it('renders reader dark room variant and custom size correctly', () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '阅读设置',
        variant: 'reader',
        size: 'lg',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    const panel = wrapper.find('.modal-panel')
    expect(panel.exists()).toBe(true)
    expect(panel.classes()).toContain('is-reader')
    expect(panel.classes()).toContain('size-lg')
    // By default, watermark is disabled in reader dark room
    expect(wrapper.find('.ambient-watermark').exists()).toBe(false)
  })

  it('emits cancel on close button click and scrim click', async () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '测试弹窗',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    await wrapper.find('.modal-close').trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()

    await wrapper.find('.modal-scrim').trigger('click')
    expect(wrapper.emitted('cancel')?.length).toBe(2)
  })

  it('emits cancel on Escape keydown', async () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '测试键盘弹窗',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
      attachTo: document.body,
    })

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('cancel')).toBeTruthy()
    wrapper.unmount()
  })

  it('traps focus on Tab and Shift+Tab keydown', async () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '焦点测试',
      },
      slots: {
        default: '<button class="inner-btn">内部按钮</button>',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
      attachTo: document.body,
    })

    const closeBtn = wrapper.find<HTMLButtonElement>('.modal-close').element
    const innerBtn = wrapper.find<HTMLButtonElement>('.inner-btn').element

    // When focus is at last element (innerBtn), pressing Tab should cycle to first (closeBtn)
    innerBtn.focus()
    expect(document.activeElement).toBe(innerBtn)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab' }))
    expect(document.activeElement).toBe(closeBtn)

    // When focus is at first element (closeBtn), Shift+Tab should cycle to last (innerBtn)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true }))
    expect(document.activeElement).toBe(innerBtn)

    wrapper.unmount()
  })
})

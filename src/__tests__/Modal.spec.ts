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

  it('renders native <dialog> with closedby="any" and syncs toggle events', async () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '原生对话框测试',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    const dialog = wrapper.find('dialog.modal-dialog')
    expect(dialog.exists()).toBe(true)
    expect(dialog.attributes('closedby')).toBe('any')
    expect(dialog.attributes('id')).toBeTruthy()

    const closeBtn = wrapper.find('button.modal-close')
    expect(closeBtn.attributes('command')).toBe('close')
    expect(closeBtn.attributes('commandfor')).toBe(dialog.attributes('id'))

    // Simulate native toggle event closing dialog
    const toggleEvent = new Event('toggle') as Event & { newState?: 'open' | 'closed' }
    toggleEvent.newState = 'closed'
    dialog.element.dispatchEvent(toggleEvent)

    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:open')?.[0]).toEqual([false])
  })

  it('respects closeOnBackdrop=false and triggers attention instead of cancel', async () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '不可点击遮罩关闭',
        closeOnBackdrop: false,
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    const scrim = wrapper.find('.modal-scrim')
    expect(scrim.exists()).toBe(true)
    await scrim.trigger('click')

    // Cancel should NOT have been emitted
    expect(wrapper.emitted('cancel')).toBeFalsy()

    // Panel should have received is-shaking class
    expect(wrapper.find('.modal-panel').classes()).toContain('is-shaking')
  })

  it('respects closeOnEsc=false and preventClose=true', async () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '完全强制进行中',
        preventClose: true,
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
      attachTo: document.body,
    })

    // Close button should not be rendered
    expect(wrapper.find('.modal-close').exists()).toBe(false)

    // Esc should not close
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('cancel')).toBeFalsy()

    // Scrim click should not close
    await wrapper.find('.modal-scrim').trigger('click')
    expect(wrapper.emitted('cancel')).toBeFalsy()

    expect(wrapper.find('.modal-panel').classes()).toContain('is-shaking')
    wrapper.unmount()
  })

  it('hides close button when showCloseButton=false', () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '无关闭按钮',
        showCloseButton: false,
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    expect(wrapper.find('.modal-close').exists()).toBe(false)
  })

  it('restores previous active element focus on close and unmount', async () => {
    const triggerBtn = document.createElement('button')
    triggerBtn.id = 'trigger-btn'
    document.body.appendChild(triggerBtn)
    triggerBtn.focus()
    expect(document.activeElement).toBe(triggerBtn)

    const wrapper = mount(Modal, {
      props: {
        open: true,
        title: '焦点记忆归还测试',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
      attachTo: document.body,
    })

    // Close modal
    await wrapper.find('.modal-close').trigger('click')
    wrapper.unmount()

    expect(document.activeElement).toBe(triggerBtn)
    document.body.removeChild(triggerBtn)
  })

  it('uses aria-label fallback when no title is provided', () => {
    const wrapper = mount(Modal, {
      props: {
        open: true,
        ariaLabel: '无障碍浮层描述',
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    const dialog = wrapper.find('dialog.modal-dialog')
    expect(dialog.attributes('aria-label')).toBe('无障碍浮层描述')
    expect(dialog.attributes('aria-labelledby')).toBeUndefined()
  })
})

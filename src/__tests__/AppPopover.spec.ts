/**
 * @file AppPopover.spec.ts
 * @description 单元测试验证 AppPopover 弹出层组件在受控（defineModel / open）与非受控交互下的状态流转与事件派发契约。
 */

import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AppPopover from '@/components/AppPopover.vue'

describe('AppPopover component', () => {
  it('renders trigger slot and popover panel with correct classes', () => {
    const wrapper = mount(AppPopover, {
      props: {
        open: false,
        side: 'bottom',
        align: 'start',
      },
      slots: {
        default: '<button class="test-trigger">Trigger</button>',
        content: '<div class="test-content">Popover Content</div>',
      },
    })

    expect(wrapper.find('.test-trigger').exists()).toBe(true)
    const panel = wrapper.find('.app-popover-panel')
    expect(panel.exists()).toBe(true)
    expect(panel.find('.test-content').exists()).toBe(true)
    expect(panel.classes()).toContain('side-bottom')
    expect(panel.classes()).toContain('align-start')
    expect(panel.classes()).not.toContain('is-open')
  })

  it('synchronizes open state when controlled externally via props/v-model', async () => {
    const wrapper = mount(AppPopover, {
      props: {
        open: false,
      },
      slots: {
        default: '<button class="test-trigger">Trigger</button>',
        content: '<div class="test-content">Popover Content</div>',
      },
    })

    const panel = wrapper.find('.app-popover-panel')
    expect(panel.classes()).not.toContain('is-open')

    // 模拟外部响应式变量变更为 true (v-model:open)
    await wrapper.setProps({ open: true } as Record<string, unknown>)
    expect(panel.classes()).toContain('is-open')
    expect(wrapper.emitted('open')).toBeDefined()
    expect(wrapper.emitted('open')?.length).toBe(1)

    // 模拟外部响应式变量变更为 false
    await wrapper.setProps({ open: false } as Record<string, unknown>)
    expect(panel.classes()).not.toContain('is-open')
    expect(wrapper.emitted('close')).toBeDefined()
    expect(wrapper.emitted('close')?.length).toBe(1)
  })

  it('toggles open state when clicking trigger in click mode', async () => {
    const wrapper = mount(AppPopover, {
      props: {
        open: false,
        trigger: 'click',
      },
      slots: {
        default: '<button class="test-btn">Toggle</button>',
        content: '<div>Content</div>',
      },
    })

    const triggerWrap = wrapper.find('.app-popover-trigger')
    await triggerWrap.trigger('click')

    expect(wrapper.emitted('update:open')).toBeDefined()
    expect(wrapper.emitted('update:open')?.[0]).toEqual([true])
  })

  it('exposes imperative open, close, toggle, and isOpen methods', async () => {
    const wrapper = mount(AppPopover, {
      props: {
        open: false,
      },
      slots: {
        default: '<button class="test-btn">Trigger</button>',
        content: '<div>Content</div>',
      },
    })

    const vm = wrapper.vm as unknown as {
      open: () => void
      close: () => void
      toggle: () => void
      isOpen: boolean
    }

    expect(vm.isOpen).toBe(false)
    vm.open()
    await nextTick()
    expect(wrapper.emitted('update:open')?.[0]).toEqual([true])

    await wrapper.setProps({ open: true } as Record<string, unknown>)
    expect(vm.isOpen).toBe(true)

    vm.close()
    await nextTick()
    expect(wrapper.emitted('update:open')).toContainEqual([false])
  })
})

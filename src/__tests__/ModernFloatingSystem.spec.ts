import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import Tooltip from '@/components/Tooltip.vue'
import AppTooltip from '@/components/AppTooltip.vue'
import AppPopover from '@/components/AppPopover.vue'
import AppDropdown from '@/components/AppDropdown.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'
import SegmentedTabs from '@/components/SegmentedTabs.vue'
import type { DropdownOption } from '@/types'

describe('Modern Floating System', () => {
  describe('Tooltip & AppTooltip', () => {
    it('defaults to lazy: true (zero-DOM) and mounts popover=hint tip element on hover', async () => {
      vi.useFakeTimers()
      const wrapper = mount(Tooltip, {
        props: {
          tip: '提示信息说明',
          side: 'top',
          align: 'center',
          delay: 50,
        },
        slots: {
          default: '<button class="test-trigger">悬停我</button>',
        },
      })

      const trigger = wrapper.find('.tooltip__trigger')
      expect(trigger.exists()).toBe(true)
      // 默认状态下 0 DOM 挂载
      expect(wrapper.find('.tooltip__tip').exists()).toBe(false)

      await wrapper.find('.tooltip-wrapper').trigger('mouseenter')
      vi.advanceTimersByTime(50)
      await wrapper.vm.$nextTick()

      const tip = wrapper.find('.tooltip__tip')
      expect(tip.exists()).toBe(true)
      expect(tip.attributes('popover')).toBe('hint')
      expect(tip.attributes('role')).toBe('tooltip')
      expect(tip.text()).toBe('提示信息说明')

      const describedBy = trigger.attributes('aria-describedby')
      expect(describedBy).toBe(tip.attributes('id'))
      expect(tip.classes()).toContain('side-top')
      expect(tip.classes()).toContain('align-center')

      vi.useRealTimers()
    })

    it('applies side and align classes for dynamic arrow targeting when lazy=false', () => {
      const wrapper = mount(Tooltip, {
        props: {
          tip: '说明',
          side: 'top',
          align: 'end',
          lazy: false,
        },
        slots: {
          default: '<button>按钮</button>',
        },
      })

      const tip = wrapper.find('.tooltip__tip')
      expect(tip.classes()).toContain('side-top')
      expect(tip.classes()).toContain('align-end')
    })

    it('supports AppTooltip alias with rich content slot', () => {
      const wrapper = mount(AppTooltip, {
        props: {
          side: 'bottom',
          lazy: false,
        },
        slots: {
          default: '<span class="target">文本</span>',
          content: '<strong class="rich">富文本内容</strong>',
        },
      })

      const tip = wrapper.find('.tooltip__tip')
      expect(tip.find('.rich').exists()).toBe(true)
      expect(tip.text()).toContain('富文本内容')
    })

    it('keeps tooltip open when cursor moves onto the tip element (WCAG 1.4.13 hoverable)', async () => {
      vi.useFakeTimers()
      const wrapper = mount(Tooltip, {
        props: {
          tip: '说明文本',
          delay: 50,
          lazy: false,
        },
        slots: {
          default: '<button class="trigger">悬停</button>',
        },
      })

      const root = wrapper.find('.tooltip-wrapper')

      // 移入触发元素
      await root.trigger('mouseenter')
      vi.advanceTimersByTime(50)
      await wrapper.vm.$nextTick()

      const tip = wrapper.find('.tooltip__tip')
      expect(tip.exists()).toBe(true)
      expect(tip.classes()).toContain('is-visible')

      // 移出触发元素（触发 150ms 缓冲计时）
      await root.trigger('mouseleave')

      // 50ms 内指针划入气泡本身（安全桥连通）
      vi.advanceTimersByTime(50)
      await tip.trigger('mouseenter')

      // 推进 200ms（已超过 150ms 缓冲延时）
      vi.advanceTimersByTime(200)
      await wrapper.vm.$nextTick()
      // 气泡因处于悬停保护期而依然保持展开
      expect(tip.classes()).toContain('is-visible')

      // 最终光标移出气泡
      await tip.trigger('mouseleave')
      vi.advanceTimersByTime(150)
      await wrapper.vm.$nextTick()
      expect(tip.classes()).not.toContain('is-visible')

      vi.useRealTimers()
    })

    it('dynamically flips actualSide class and data-side when collision causes vertical inversion', async () => {
      vi.useFakeTimers()
      const wrapper = mount(Tooltip, {
        props: {
          tip: '顶部提示',
          side: 'top',
          delay: 0,
          lazy: false,
        },
        slots: {
          default: '<button class="trigger">按钮</button>',
        },
      })

      const trigger = wrapper.find('.tooltip__trigger')
      const tip = wrapper.find('.tooltip__tip')

      // 模拟视口顶部空间不足导致锚点渲染在下方 (tip.top >= trigger.top)
      vi.spyOn(trigger.element, 'getBoundingClientRect').mockReturnValue({
        top: 50,
        bottom: 70,
        left: 100,
        right: 150,
        width: 50,
        height: 20,
        x: 100,
        y: 50,
        toJSON: () => {},
      })
      vi.spyOn(tip.element, 'getBoundingClientRect').mockReturnValue({
        top: 80,
        bottom: 180,
        left: 100,
        right: 250,
        width: 150,
        height: 100,
        x: 100,
        y: 80,
        toJSON: () => {},
      })

      await wrapper.find('.tooltip-wrapper').trigger('mouseenter')
      vi.advanceTimersByTime(10)
      await wrapper.vm.$nextTick()

      // 实际渲染在下方，实际类名与属性自适应更新为 side-bottom，确保箭头指向正确的上方
      expect(tip.classes()).toContain('side-bottom')
      expect(tip.attributes('data-side')).toBe('bottom')

      vi.useRealTimers()
    })
  })

  describe('AppPopover', () => {
    it('renders popover="auto" panel and handles toggle', async () => {
      const wrapper = mount(AppPopover, {
        props: {
          open: false,
          side: 'bottom',
          align: 'start',
        },
        slots: {
          default:
            '<template #default="{ toggle }"><button class="pop-btn" @click="toggle">展开</button></template>',
          content: '<div class="pop-content">浮层面板内容</div>',
        },
      })

      const popoverPanel = wrapper.find('.app-popover-panel')
      expect(popoverPanel.exists()).toBe(true)
      expect(popoverPanel.attributes('popover')).toBe('auto')
      expect(popoverPanel.classes()).not.toContain('is-open')

      await wrapper.find('.pop-btn').trigger('click')
      expect(wrapper.emitted('update:open')?.[0]).toEqual([true])
    })

    it('supports custom role prop on popover panel', () => {
      const wrapper = mount(AppPopover, {
        props: {
          role: 'dialog',
          ariaLabel: '测试对话框',
        },
      })
      const panel = wrapper.find('.app-popover-panel')
      expect(panel.attributes('role')).toBe('dialog')
      expect(panel.attributes('aria-label')).toBe('测试对话框')
    })
  })

  describe('AppDropdown', () => {
    const options: DropdownOption[] = [
      { key: 'opt1', label: '选项一', hint: '快捷键 1' },
      { key: 'opt2', label: '选项二', icon: 'check' },
      { key: 'sep', label: '', separator: true },
      { key: 'danger', label: '危险操作', danger: true },
    ]

    it('renders trigger text and options correctly', () => {
      const wrapper = mount(AppDropdown, {
        props: {
          options,
          modelValue: 'opt1',
        },
      })

      const triggerLabel = wrapper.find('.trigger-label')
      expect(triggerLabel.text()).toBe('选项一')

      const items = wrapper.findAll('.dropdown-item')
      expect(items.length).toBe(3) // 3 项 + 1 分割线
      expect(items[0]?.text()).toContain('选项一')
      expect(items[0]?.text()).toContain('快捷键 1')
      expect(items[2]?.classes()).toContain('is-danger')
    })

    it('selects option and emits update:modelValue and change', async () => {
      const wrapper = mount(AppDropdown, {
        props: {
          options,
          modelValue: 'opt1',
        },
      })

      const items = wrapper.findAll('.dropdown-item')
      await items[1]?.trigger('click')

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['opt2'])
      expect(wrapper.emitted('change')?.[0]).toEqual(['opt2'])
      expect(wrapper.emitted('select')?.[0]?.[0]).toMatchObject({
        key: 'opt2',
        label: '选项二',
      })
    })

    it('navigates with keyboard ArrowDown / ArrowUp / Enter', async () => {
      const wrapper = mount(AppDropdown, {
        props: {
          options,
          modelValue: 'opt1',
        },
      })

      const trigger = wrapper.find('.dropdown-trigger')
      await trigger.trigger('click') // 打开下拉
      await trigger.trigger('keydown', { key: 'ArrowDown' })

      const activeItem = wrapper.find('.dropdown-item.is-active')
      expect(activeItem.text()).toContain('选项二')

      await trigger.trigger('keydown', { key: 'Enter' })
      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['opt2'])
    })

    it('scrolls active item into view during continuous keyboard navigation', async () => {
      const scrollMock = vi.fn<() => void>()
      window.HTMLElement.prototype.scrollIntoView = scrollMock

      const wrapper = mount(AppDropdown, {
        props: {
          options,
          modelValue: 'opt1',
        },
      })

      const trigger = wrapper.find('.dropdown-trigger')
      await trigger.trigger('click')
      await trigger.trigger('keydown', { key: 'ArrowDown' })

      expect(scrollMock).toHaveBeenCalled()
    })
    it('does not render item-leading for action menu without icons', () => {
      const actionOptions: DropdownOption[] = [
        { key: 'remove', label: '移除本地缓存…', danger: true, hint: '不可撤销' },
      ]
      const wrapper = mount(AppDropdown, {
        props: {
          options: actionOptions,
        },
      })

      expect(wrapper.find('.item-leading').exists()).toBe(false)
      const label = wrapper.find('.item-label')
      expect(label.text()).toBe('移除本地缓存…')
    })
  })

  describe('ThemeSelect Integration', () => {
    it('wraps AppDropdown and displays selected option label even when label prop is provided', async () => {
      const options = [
        { value: 'recent', label: '最近收录' },
        { value: 'title', label: '标题' },
      ]

      const wrapper = mount(ThemeSelect, {
        props: {
          label: '排序',
          modelValue: 'recent',
          options,
        },
      })

      const triggerLabel = wrapper.find('.trigger-label')
      expect(triggerLabel.text()).toBe('最近收录') // 不应显示静态的“排序”，应展示选中的“最近收录”

      const items = wrapper.findAll('.dropdown-item')
      await items[1]?.trigger('click')

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['title'])
      expect(wrapper.emitted('change')?.[0]).toEqual(['title'])
    })
  })

  describe('SegmentedTabs with Anchor Indicator', () => {
    it('sets dynamic anchorName on active tab button', () => {
      const wrapper = mount(SegmentedTabs, {
        props: {
          modelValue: 'tab1',
          items: [
            { key: 'tab1', label: '标签一' },
            { key: 'tab2', label: '标签二' },
          ],
        },
      })

      const tabs = wrapper.findAll('.segmented-tab')
      const activeTab = tabs[0]!
      const inactiveTab = tabs[1]!

      expect(activeTab.classes()).toContain('is-active')
      expect(activeTab.attributes('style')).toContain('anchor-name:')
      expect(inactiveTab.attributes('style')).toBeUndefined()
    })
  })
})

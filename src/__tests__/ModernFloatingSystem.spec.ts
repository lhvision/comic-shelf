import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import Tooltip from '@/components/Tooltip.vue'
import AppTooltip from '@/components/AppTooltip.vue'
import AppPopover from '@/components/AppPopover.vue'
import AppDropdown from '@/components/AppDropdown.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'
import SegmentedTabs from '@/components/SegmentedTabs.vue'

describe('Modern Floating System', () => {
  describe('Tooltip & AppTooltip', () => {
    it('renders trigger element and popover=hint tip element with accessibility attributes', () => {
      const wrapper = mount(Tooltip, {
        props: {
          tip: '提示信息说明',
          side: 'top',
          align: 'center',
        },
        slots: {
          default: '<button class="test-trigger">悬停我</button>',
        },
      })

      const trigger = wrapper.find('.tooltip__trigger')
      const tip = wrapper.find('.tooltip__tip')

      expect(trigger.exists()).toBe(true)
      expect(tip.exists()).toBe(true)
      expect(tip.attributes('popover')).toBe('hint')
      expect(tip.attributes('role')).toBe('tooltip')
      expect(tip.text()).toBe('提示信息说明')

      const describedBy = trigger.attributes('aria-describedby')
      expect(describedBy).toBe(tip.attributes('id'))
    })

    it('supports AppTooltip alias with rich content slot', () => {
      const wrapper = mount(AppTooltip, {
        props: {
          side: 'bottom',
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
  })

  describe('AppDropdown', () => {
    const options = [
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
      const actionOptions = [
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

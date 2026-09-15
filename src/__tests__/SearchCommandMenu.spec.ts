import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import SearchCommandMenu from '@/components/library/SearchCommandMenu.vue'
import { AVAILABLE_COMMANDS } from '@/composables/useSearchCommands'

describe('SearchCommandMenu.vue', () => {
  it('does not render popover when open is false', () => {
    const wrapper = mount(SearchCommandMenu, {
      props: {
        open: false,
        commands: AVAILABLE_COMMANDS,
        focusedIndex: 0,
      },
    })

    expect(wrapper.find('.command-menu-popover').exists()).toBe(false)
  })

  it('renders popover with listbox role and commands when open is true', () => {
    const wrapper = mount(SearchCommandMenu, {
      props: {
        open: true,
        commands: AVAILABLE_COMMANDS,
        focusedIndex: 1,
      },
    })

    expect(wrapper.find('.command-menu-popover').exists()).toBe(true)
    expect(wrapper.find('.header-title').text()).toBe('快捷指令选单')

    const listbox = wrapper.find('[role="listbox"]')
    expect(listbox.exists()).toBe(true)

    const items = wrapper.findAll('.menu-item')
    expect(items.length).toBe(AVAILABLE_COMMANDS.length)

    // Verify focused index highlight
    expect(items[1]?.classes()).toContain('is-focused')
    expect(items[1]?.attributes('aria-selected')).toBe('true')
    expect(items[0]?.classes()).not.toContain('is-focused')
    expect(items[0]?.attributes('aria-selected')).toBe('false')
  })

  it('emits select event on item click', async () => {
    const wrapper = mount(SearchCommandMenu, {
      props: {
        open: true,
        commands: AVAILABLE_COMMANDS,
        focusedIndex: 0,
      },
    })

    const firstItem = wrapper.findAll('.menu-item')[0]
    await firstItem?.trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')?.[0]?.[0]).toEqual(AVAILABLE_COMMANDS[0])
  })

  it('emits update:focusedIndex on mouseenter', async () => {
    const wrapper = mount(SearchCommandMenu, {
      props: {
        open: true,
        commands: AVAILABLE_COMMANDS,
        focusedIndex: 0,
      },
    })

    const secondItem = wrapper.findAll('.menu-item')[1]
    await secondItem?.trigger('mouseenter')

    expect(wrapper.emitted('update:focusedIndex')).toBeTruthy()
    expect(wrapper.emitted('update:focusedIndex')?.[0]?.[0]).toBe(1)
  })

  it('renders empty message when commands list is empty', () => {
    const wrapper = mount(SearchCommandMenu, {
      props: {
        open: true,
        commands: [],
        focusedIndex: 0,
      },
    })

    expect(wrapper.find('.menu-empty').exists()).toBe(true)
    expect(wrapper.find('.menu-empty').text()).toBe('未找到匹配的快捷指令')
  })
})

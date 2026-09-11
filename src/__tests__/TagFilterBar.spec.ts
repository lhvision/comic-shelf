import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import TagFilterBar from '@/components/library/TagFilterBar.vue'

describe('TagFilterBar', () => {
  const tagCounts: Array<[string, number]> = [
    ['tag1', 10],
    ['tag2', 9],
    ['tag3', 8],
    ['tag4', 7],
    ['tag5', 6],
    ['tag6', 5],
    ['tag7', 4],
    ['tag8', 3],
    ['tag9', 2],
    ['tag10', 1],
  ]

  it('renders primary tags and more button when tags exceed 8', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const directButtons = wrapper.findAll('.filter-cluster > .chip-button')
    // favorite (1) + all (1) + 8 primary = 10 direct chip buttons
    expect(directButtons.length).toBe(10)
    expect(wrapper.find('.more-tags').text()).toContain('更多 · 2')

    // Reading status tabs
    const statusTabs = wrapper.findAll('.segmented-tab')
    expect(statusTabs.length).toBe(3)
    expect(statusTabs[0]?.text()).toBe('全部')
    expect(statusTabs[1]?.text()).toBe('在读')
    expect(statusTabs[2]?.text()).toBe('已读')

    // Overflow popover exists in DOM
    const overflowCluster = wrapper.find('.overflow-cluster')
    expect(overflowCluster.exists()).toBe(true)
    expect(overflowCluster.findAll('.chip-button').length).toBe(2)
  })

  it('toggles trayExpanded on more button click and updates label', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
        trayExpanded: false,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    expect(moreBtn.text()).toContain('更多 · 2')
    await moreBtn.trigger('click')

    expect(wrapper.emitted('update:trayExpanded')?.[0]).toEqual([true])

    await wrapper.setProps({ trayExpanded: true } as Record<string, unknown>)
    expect(wrapper.find('.more-tags').text()).toContain('收起标签')

    // Check overflow tags
    const overflowTags = wrapper.find('.overflow-cluster').findAll('.chip-button')
    expect(overflowTags.length).toBe(2)
    expect(overflowTags[0]?.text()).toContain('tag9')
    expect(overflowTags[1]?.text()).toContain('tag10')
  })

  it('emits selectTag when an overflow tag is clicked without closing popover', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
        trayExpanded: true,
      },
    })

    const overflowTag = wrapper.find('.overflow-cluster').findAll('.chip-button')[0]
    await overflowTag?.trigger('click')

    expect(wrapper.emitted('selectTag')?.[0]).toEqual(['tag9'])
    // Popover stays open for consecutive tag selection
    expect(wrapper.emitted('update:trayExpanded')).toBeUndefined()
  })

  it('emits toggleFavorites when favorite button is clicked', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const favBtn = wrapper.find('.favorite-filter')
    await favBtn.trigger('click')

    expect(wrapper.emitted('toggleFavorites')).toBeTruthy()
  })

  it('emits update:readingStatus when segmented tabs are clicked', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        readingStatus: 'all',
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const tabs = wrapper.findAll('.segmented-tab')
    expect(tabs[0]?.classes()).toContain('is-active')

    // Click "在读"
    await tabs[1]?.trigger('click')
    expect(wrapper.emitted('update:readingStatus')?.[0]).toEqual(['reading'])

    // Click "已读"
    await tabs[2]?.trigger('click')
    expect(wrapper.emitted('update:readingStatus')?.[1]).toEqual(['completed'])

    // Controlled prop update
    await wrapper.setProps({ readingStatus: 'completed' } as Record<string, unknown>)
    expect(tabs[2]?.classes()).toContain('is-active')
  })

  it('indicates active state on more button when activeTag is in overflow tags', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: 'tag9',
        tagCounts,
        filteredCount: 2,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    expect(moreBtn.classes()).toContain('is-active-filter')
    expect(moreBtn.attributes('aria-pressed')).toBe('true')
    expect(moreBtn.text()).toContain('标签：tag9')
  })

  it('updates active state on more button when activeTag changes to an overflow tag', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    expect(wrapper.find('.more-tags').classes()).not.toContain('is-active-filter')

    await wrapper.setProps({
      activeTag: 'tag10',
      filteredCount: 1,
    } as Record<string, unknown>)

    const updatedMoreBtn = wrapper.find('.more-tags')
    expect(updatedMoreBtn.classes()).toContain('is-active-filter')
    expect(updatedMoreBtn.attributes('aria-pressed')).toBe('true')
    expect(updatedMoreBtn.text()).toContain('标签：tag10')
  })

  it('supports two-way binding via trayExpanded model', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
        trayExpanded: false,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    await moreBtn.trigger('click')

    expect(wrapper.emitted('update:trayExpanded')?.[0]).toEqual([true])
  })

  it('renders offline chip when offlineCount > 0 and emits toggleOffline on click', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        offlineOnly: false,
        offlineCount: 5,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const offlineBtn = wrapper.find('.offline-filter')
    expect(offlineBtn.exists()).toBe(true)
    expect(offlineBtn.text()).toContain('只看离线')
    expect(offlineBtn.text()).toContain('5')

    await offlineBtn.trigger('click')
    expect(wrapper.emitted('toggleOffline')).toHaveLength(1)
  })

  it('renders pinned active tag and clear button inside popover when overflow tag is active', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: 'tag9',
        tagCounts,
        filteredCount: 2,
      },
    })

    const activeRow = wrapper.find('.overflow-active-row')
    expect(activeRow.exists()).toBe(true)
    expect(activeRow.text()).toContain('tag9')
    expect(activeRow.text()).toContain('当前在看：')

    const clearBtn = wrapper.find('.overflow-clear-btn')
    expect(clearBtn.exists()).toBe(true)
    expect(clearBtn.text()).toContain('清除筛选')
  })

  it('clears overflow filter when clear button inside popover is clicked without closing popover', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: 'tag9',
        tagCounts,
        filteredCount: 2,
        trayExpanded: true,
      },
    })

    const clearBtn = wrapper.find('.overflow-clear-btn')
    await clearBtn.trigger('click')

    expect(wrapper.emitted('selectTag')).toContainEqual([''])
    expect(wrapper.emitted('clearTag')).toHaveLength(1)
    // Popover remains open so user can pick another tag
    expect(wrapper.emitted('update:trayExpanded')).toBeUndefined()
  })
})

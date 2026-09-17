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

  it('emits update:activeTags when an overflow tag is clicked without closing popover', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        tagCounts,
        filteredCount: 10,
        trayExpanded: true,
      },
    })

    const overflowTag = wrapper.find('.overflow-cluster').findAll('.chip-button')[0]
    await overflowTag?.trigger('click')

    expect(wrapper.emitted('update:activeTags')?.[0]).toEqual([['tag9']])
    // Popover stays open for consecutive tag selection
    expect(wrapper.emitted('update:trayExpanded')).toBeUndefined()
  })

  it('emits toggleFavorites when favorite button is clicked', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
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

  it('indicates active state on more button when activeTags includes overflow tag', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTags: ['tag9'],
        tagCounts,
        filteredCount: 2,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    expect(moreBtn.classes()).toContain('is-active-filter')
    expect(moreBtn.attributes('aria-pressed')).toBe('true')
    expect(moreBtn.text()).toContain('标签：tag9')
  })

  it('updates active state on more button when activeTags changes to an overflow tag', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTags: [],
        tagCounts,
        filteredCount: 10,
      },
    })

    expect(wrapper.find('.more-tags').classes()).not.toContain('is-active-filter')

    await wrapper.setProps({
      activeTags: ['tag10'],
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
        tagCounts,
        filteredCount: 10,
        trayExpanded: false,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    await moreBtn.trigger('click')

    expect(wrapper.emitted('update:trayExpanded')?.[0]).toEqual([true])
  })

  it('does not render manual offline filter chip in toolbar (zero-toggle resilience)', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        tagCounts,
        filteredCount: 10,
      },
    })

    expect(wrapper.find('.offline-filter').exists()).toBe(false)
  })

  it('renders pinned active tag and clear button inside popover when overflow tag is active', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTags: ['tag9'],
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
        activeTags: ['tag9'],
        tagCounts,
        filteredCount: 2,
        trayExpanded: true,
      },
    })

    const clearBtn = wrapper.find('.overflow-clear-btn')
    await clearBtn.trigger('click')

    expect(wrapper.emitted('update:activeTags')).toContainEqual([[]])
    // Popover remains open so user can pick another tag
    expect(wrapper.emitted('update:trayExpanded')).toBeUndefined()
  })

  it('supports multiple activeTags and toggles individual tags on/off', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTags: ['tag1'],
        tagCounts,
        filteredCount: 5,
      },
    })

    const directButtons = wrapper.findAll('.filter-cluster > .chip-button')
    // Buttons: favorite (0), all (1), tag1 (2), tag2 (3) ...
    // Check "全部" is not pressed when activeTags is non-empty
    expect(directButtons[1]?.attributes('aria-pressed')).toBe('false')
    // tag1 is pressed
    expect(directButtons[2]?.attributes('aria-pressed')).toBe('true')
    // tag2 is not pressed
    expect(directButtons[3]?.attributes('aria-pressed')).toBe('false')

    // Click unselected tag2 -> emits update:activeTags with ['tag1', 'tag2']
    await directButtons[3]?.trigger('click')
    expect(wrapper.emitted('update:activeTags')?.[0]).toEqual([['tag1', 'tag2']])

    // Click selected tag1 -> emits update:activeTags with ['tag2'] (since tag2 was added)
    await directButtons[2]?.trigger('click')
    expect(wrapper.emitted('update:activeTags')?.[1]).toEqual([['tag2']])

    // Click "全部" -> clears all activeTags
    await directButtons[1]?.trigger('click')
    expect(wrapper.emitted('update:activeTags')?.[2]).toEqual([[]])
  })

  it('displays composite tag label in more button when multiple overflow tags are selected', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTags: ['tag9', 'tag10'],
        tagCounts,
        filteredCount: 1,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    expect(moreBtn.classes()).toContain('is-active-filter')
    expect(moreBtn.attributes('aria-pressed')).toBe('true')
    expect(moreBtn.text()).toContain('更多 · 2 (已选 2)')

    // Check filter note at bottom shows joined tags
    const filterNote = wrapper.find('.filter-note')
    expect(filterNote.text()).toContain('正在查看标签「tag9 · tag10」的 1 本')
  })

  it('blocks selecting more than 5 tags and removes tag on deselect', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTags: ['tag1', 'tag2', 'tag3', 'tag4', 'tag5'],
        tagCounts,
        filteredCount: 1,
      },
    })

    const directButtons = wrapper.findAll('.filter-cluster > .chip-button')
    // Buttons: favorite (0), all (1), tag1 (2), tag2 (3), tag3 (4), tag4 (5), tag5 (6), tag6 (7)
    // Click 6th tag (tag6) -> should be blocked by MAX_SELECTED_TAGS = 5
    await directButtons[7]?.trigger('click')
    expect(wrapper.emitted('update:activeTags')).toBeUndefined()

    // Test deselect: clicking an already selected tag (tag1) deselects it and emits remaining
    await directButtons[2]?.trigger('click')
    expect(wrapper.emitted('update:activeTags')?.[0]).toEqual([['tag2', 'tag3', 'tag4', 'tag5']])
  })
})

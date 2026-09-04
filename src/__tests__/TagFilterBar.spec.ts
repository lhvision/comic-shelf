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

    const primaryButtons = wrapper.find('.filter-cluster').findAll('.chip-button')
    // favorite (1) + completed (1) + all (1) + 8 primary + more button (1) = 12 buttons
    expect(primaryButtons.length).toBe(12)
    expect(wrapper.find('.more-tags').text()).toContain('更多 · 2')

    // Tray exists in DOM but collapsed
    const tray = wrapper.find('.more-tags-tray')
    expect(tray.exists()).toBe(true)
    expect(tray.classes()).not.toContain('is-expanded')
    expect(tray.findAll('.chip-button').length).toBe(2)
  })

  it('expands tray and reveals overflow tags on more button click', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    await moreBtn.trigger('click')

    const tray = wrapper.find('.more-tags-tray')
    expect(tray.classes()).toContain('is-expanded')
    expect(moreBtn.text()).toContain('收起标签')

    // Check overflow tags
    const overflowTags = tray.findAll('.chip-button')
    expect(overflowTags.length).toBe(2)
    expect(overflowTags[0]?.text()).toContain('tag9')
    expect(overflowTags[1]?.text()).toContain('tag10')
  })

  it('emits selectTag when an overflow tag is clicked', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const moreBtn = wrapper.find('.more-tags')
    await moreBtn.trigger('click')

    const tray = wrapper.find('.more-tags-tray')
    const overflowTag = tray.findAll('.chip-button')[0]
    await overflowTag?.trigger('click')

    expect(wrapper.emitted('selectTag')?.[0]).toEqual(['tag9'])
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

  it('emits toggleCompleted when completed button is clicked', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        completedOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const completedBtn = wrapper.find('.completed-filter')
    expect(completedBtn.attributes('aria-pressed')).toBe('false')
    await completedBtn.trigger('click')

    expect(wrapper.emitted('toggleCompleted')).toBeTruthy()

    await wrapper.setProps({ completedOnly: true } as Record<string, unknown>)
    expect(completedBtn.attributes('aria-pressed')).toBe('true')
  })

  it('auto-expands tray when initialized with activeTag in overflow tags', () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: 'tag9',
        tagCounts,
        filteredCount: 2,
      },
    })

    const tray = wrapper.find('.more-tags-tray')
    expect(tray.classes()).toContain('is-expanded')
    expect(wrapper.find('.more-tags').text()).toContain('收起标签')
  })

  it('auto-expands tray when activeTag prop changes to an overflow tag', async () => {
    const wrapper = mount(TagFilterBar, {
      props: {
        favoritesOnly: false,
        activeTag: '',
        tagCounts,
        filteredCount: 10,
      },
    })

    const tray = wrapper.find('.more-tags-tray')
    expect(tray.classes()).not.toContain('is-expanded')

    await wrapper.setProps({
      activeTag: 'tag10',
      filteredCount: 1,
    } as Record<string, unknown>)
    expect(tray.classes()).toContain('is-expanded')
  })
})

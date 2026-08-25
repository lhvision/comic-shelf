import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ComicGrid from '@/components/library/ComicGrid.vue'
import type { LibrarySummary } from '@/types'

// Mock subcomponents
vi.mock('@/components/ComicCard.vue', () => ({
  default: {
    name: 'ComicCard',
    props: ['comic', 'cache', 'searchMatch'],
    template: '<div class="mock-comic-card">{{ comic.title }}</div>',
  },
}))

vi.mock('@/components/HtmlCanvasCard.vue', () => ({
  default: {
    name: 'HtmlCanvasCard',
    props: ['comic', 'enabled', 'cache'],
    template: '<div class="mock-canvas-card">{{ comic.title }}</div>',
  },
}))

function makeComics(count: number): LibrarySummary[] {
  return Array.from({ length: count }, (_, i) => ({
    source: 'jm',
    source_id: `id_${i + 1}`,
    display_id: `${i + 1}`,
    title: `漫画标题 ${i + 1}`,
    cover_paths: ['/cover1.webp', '/cover2.webp', '/cover3.webp', '/cover4.webp'],
    page_count: 20,
    cached_pages: 20,
    favorite: false,
    authors: ['作者'],
    works: [],
    actors: [],
    tags: ['同人'],
    views: '100',
    likes: '10',
    uploaded_at: '2026-01-01T00:00:00Z',
    published_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    imported_at: '2026-01-01T00:00:00Z',
    cover_count: 4,
  }))
}

describe('ComicGrid', () => {
  it('renders skeletons during loading', () => {
    const wrapper = mount(ComicGrid, {
      props: {
        loading: true,
        items: [],
        useCanvas: false,
        hasAnyItems: false,
      },
    })

    expect(wrapper.findAll('.skeleton-card').length).toBe(6)
  })

  it('renders empty shelf when not loading and empty', () => {
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: [],
        useCanvas: false,
        hasAnyItems: false,
      },
    })

    expect(wrapper.find('.empty-shelf').exists()).toBe(true)
    expect(wrapper.text()).toContain('书架还是空的')
  })

  it('chunks items by batchStep (default 12) for DOM cards and shows sentinel', async () => {
    const comics = makeComics(25)
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: comics,
        useCanvas: false,
        hasAnyItems: true,
        batchStep: 12,
      },
    })

    // Initially only 12 items rendered
    expect(wrapper.findAll('.mock-comic-card').length).toBe(12)
    const sentinel = wrapper.find('.shelf-sentinel')
    expect(sentinel.exists()).toBe(true)
    expect(sentinel.text()).toContain('已呈现 12 / 25 本')

    // Click load more button to expand next batch
    await sentinel.find('button').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(24)
    expect(wrapper.find('.shelf-sentinel').text()).toContain('已呈现 24 / 25 本')

    // Click load more button again
    await wrapper.find('.shelf-sentinel button').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(25)
    expect(wrapper.find('.shelf-sentinel').exists()).toBe(false)
  })

  it('resets visible items when items prop changes', async () => {
    const comics1 = makeComics(25)
    const wrapper = mount(ComicGrid, {
      props: {
        loading: false,
        items: comics1,
        useCanvas: false,
        hasAnyItems: true,
        batchStep: 12,
      },
    })

    // Click load more
    await wrapper.find('.shelf-sentinel button').trigger('click')
    expect(wrapper.findAll('.mock-comic-card').length).toBe(24)

    // Items filtered or changed to new list of 20 items
    const comics2 = makeComics(20)
    await wrapper.setProps({ items: comics2 } as Record<string, unknown>)

    // Should reset back to 12
    expect(wrapper.findAll('.mock-comic-card').length).toBe(12)
    expect(wrapper.find('.shelf-sentinel').text()).toContain('已呈现 12 / 20 本')
  })
})

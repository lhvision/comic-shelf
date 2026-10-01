import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ComicCard from '@/components/ComicCard.vue'
import type { LibrarySummary } from '@/types'

function createSampleComic(overrides: Partial<LibrarySummary> = {}): LibrarySummary {
  return {
    source: 'local',
    source_id: '20260918_010452',
    display_id: 'LOC_20260918_010452',
    title: '测试漫画',
    cover_paths: ['/cover1.webp', '/cover2.webp', '/cover3.webp', '/cover4.webp'],
    page_count: 20,
    cached_pages: 20,
    favorite: false,
    authors: ['作者'],
    works: [],
    actors: [],
    tags: ['百合', '纯爱'],
    views: '',
    likes: '',
    uploaded_at: '2026-09-18T00:00:00Z',
    published_at: '2026-09-18T00:00:00Z',
    updated_at: '2026-09-18T00:00:00Z',
    imported_at: '2026-09-18T00:00:00Z',
    cover_count: 4,
    ...overrides,
  }
}

describe('ComicCard component', () => {
  it('renders views and card-progress when views are present', () => {
    const comic = createSampleComic({
      source: 'jm',
      source_id: '1059521',
      display_id: 'JM1059521',
      views: '13K',
    })

    const wrapper = mount(ComicCard, {
      props: { comic },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
          AppTextClamp: true,
          FavoriteButton: true,
        },
      },
    })

    const foot = wrapper.find('.card-foot')
    expect(foot.exists()).toBe(true)

    const views = wrapper.find('.views')
    expect(views.exists()).toBe(true)
    expect(views.text()).toBe('13K 次观看')

    const progress = wrapper.find('.card-progress')
    expect(progress.exists()).toBe(true)
  })

  it('omits views and keeps card-progress pinned when views are absent', () => {
    const comic = createSampleComic({
      source: 'local',
      source_id: '20260918_010452',
      display_id: 'LOC_20260918_010452',
      views: '',
    })

    const wrapper = mount(ComicCard, {
      props: { comic },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
          AppTextClamp: true,
          FavoriteButton: true,
        },
      },
    })

    const foot = wrapper.find('.card-foot')
    expect(foot.exists()).toBe(true)

    const views = wrapper.find('.views')
    expect(views.exists()).toBe(false)

    const progress = wrapper.find('.card-progress')
    expect(progress.exists()).toBe(true)
  })

  it('displays clean display_id stamp on cover with title attribute', () => {
    const comic = createSampleComic({
      display_id: 'LOC_20260918_010452',
    })

    const wrapper = mount(ComicCard, {
      props: { comic },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
          AppTextClamp: true,
          FavoriteButton: true,
        },
      },
    })

    const stamp = wrapper.find('.id-stamp')
    expect(stamp.exists()).toBe(true)
    expect(stamp.text()).toBe('LOC_20260918_010452')
    expect(stamp.attributes('title')).toBe('LOC_20260918_010452')
  })

  it('coexists with reading stamp without interference when comic is in-progress', () => {
    const comic = createSampleComic({
      display_id: 'COPY_xiangyaochengweiyingzhishilizhe',
      last_page: 5,
      page_count: 2846,
    })

    const wrapper = mount(ComicCard, {
      props: { comic },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
          AppTextClamp: true,
          FavoriteButton: true,
        },
      },
    })

    const idStamp = wrapper.find('.id-stamp')
    expect(idStamp.exists()).toBe(true)
    expect(idStamp.text()).toBe('COPY_xiangyaochengweiyingzhishilizhe')
    expect(idStamp.attributes('title')).toBe('COPY_xiangyaochengweiyingzhishilizhe')

    const readingStamp = wrapper.find('.reading-stamp.is-reading')
    expect(readingStamp.exists()).toBe(true)
    expect(readingStamp.text()).toBe('5P / 2846P')
  })
})

import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderViewport from '@/components/reader/ReaderViewport.vue'
import ReaderChapterBanners from '@/components/reader/ReaderChapterBanners.vue'
import ReaderEndCard from '@/components/reader/ReaderEndCard.vue'
import { DEFAULT_SETTINGS } from '@/composables/useReaderSettings'
import type { Chapter, LibrarySummary } from '@/types'

describe('ReaderViewport', () => {
  const defaultProps = {
    settings: { ...DEFAULT_SETTINGS },
    source: 'jm',
    sourceId: '123456',
    orderedGroups: [
      { pages: [1, 2], index: 0 },
      { pages: [3, 4], index: 1 },
    ],
    showEndCard: true,
    rtlHorizontal: false,
    loadingVariant: '/loading-1.webp',
    toLocalPage: (page: number) => page,
  }

  it('renders spreads and pages based on orderedGroups', () => {
    const wrapper = mount(ReaderViewport, {
      props: defaultProps,
    })

    const spreads = wrapper.findAll('.reader-spread')
    expect(spreads.length).toBe(2)

    const pages = wrapper.findAll('.reader-page')
    expect(pages.length).toBe(4)
    expect(pages[0]?.attributes('data-page')).toBe('1')
    expect(pages[1]?.attributes('data-page')).toBe('2')
    expect(pages[2]?.attributes('data-page')).toBe('3')
    expect(pages[3]?.attributes('data-page')).toBe('4')

    const footers = wrapper.findAll('.page-footer')
    expect(footers[0]?.text()).toBe('001')
    expect(footers[1]?.text()).toBe('002')
  })

  it('emits scroll, wheel, mousemove, and readerClick events', async () => {
    const wrapper = mount(ReaderViewport, {
      props: defaultProps,
    })

    const main = wrapper.find('.reader-scroll')
    await main.trigger('scroll')
    expect(wrapper.emitted('scroll')).toBeTruthy()

    await main.trigger('wheel')
    expect(wrapper.emitted('wheel')).toBeTruthy()

    await main.trigger('touchstart')
    expect(wrapper.emitted('userInteract')).toBeTruthy()

    await main.trigger('mousemove')
    expect(wrapper.emitted('mousemove')).toBeTruthy()

    await main.trigger('click')
    expect(wrapper.emitted('readerClick')).toBeTruthy()
  })

  it('renders ReaderEndCard at the end in non-RTL mode', () => {
    const wrapper = mount(ReaderViewport, {
      props: {
        ...defaultProps,
        showEndCard: true,
        rtlHorizontal: false,
      },
    })

    const endCards = wrapper.findAllComponents({ name: 'ReaderEndCard' })
    expect(endCards.length).toBe(1)
    expect(wrapper.find('.reader-end-rtl').exists()).toBe(false)
  })

  it('renders ReaderEndCard at the start in RTL horizontal mode', () => {
    const wrapper = mount(ReaderViewport, {
      props: {
        ...defaultProps,
        showEndCard: true,
        rtlHorizontal: true,
      },
    })

    const endCardRtl = wrapper.find('.reader-end-rtl')
    expect(endCardRtl.exists()).toBe(true)
  })
})

describe('ReaderChapterBanners', () => {
  const prevChapter: Chapter = {
    id: 'ch-1',
    index: 1,
    title: '第 1 话：起点',
    page_count: 20,
    start: 1,
  }

  const nextChapter: Chapter = {
    id: 'ch-2',
    index: 2,
    title: '第 2 话：进发',
    page_count: 25,
    start: 21,
  }

  const chapterShortLabel = vi.fn<(chapter: Chapter) => string>(
    (c: Chapter) => c.title || `第 ${c.index} 話`,
  )

  it('renders prev banner with IconArrowLeft when at chapter start and prevChapter exists', async () => {
    const wrapper = mount(ReaderChapterBanners, {
      props: {
        prevChapter,
        nextChapter: null,
        atChapterStart: true,
        atChapterEnd: false,
        chapterShortLabel,
        mode: 'vertical-continuous',
      },
    })

    const prevBtn = wrapper.find('.reader-chapter-prev')
    expect(prevBtn.exists()).toBe(true)
    expect(prevBtn.text()).toContain('上一话：第 1 话：起点')
    expect(prevBtn.text()).toContain('本话首')
    expect(wrapper.findComponent({ name: 'IconArrowLeft' }).exists()).toBe(true)

    expect(wrapper.find('.reader-chapter-next').exists()).toBe(false)

    await prevBtn.trigger('click')
    expect(wrapper.emitted('prevChapter')).toBeTruthy()
  })

  it('renders next banner with IconArrowRight when at chapter end and nextChapter exists', async () => {
    const wrapper = mount(ReaderChapterBanners, {
      props: {
        prevChapter: null,
        nextChapter,
        atChapterStart: false,
        atChapterEnd: true,
        chapterShortLabel,
        mode: 'vertical-continuous',
      },
    })

    const nextBtn = wrapper.find('.reader-chapter-next')
    expect(nextBtn.exists()).toBe(true)
    expect(nextBtn.text()).toContain('本话完')
    expect(nextBtn.text()).toContain('下一话：第 2 话：进发')
    expect(wrapper.findComponent({ name: 'IconArrowRight' }).exists()).toBe(true)

    expect(wrapper.find('.reader-chapter-prev').exists()).toBe(false)

    await nextBtn.trigger('click')
    expect(wrapper.emitted('nextChapter')).toBeTruthy()
  })
})

describe('ReaderEndCard', () => {
  const dummyRecs: LibrarySummary[] = [
    {
      source: 'jm',
      source_id: '101',
      display_id: '101',
      title: 'Recommend A',
      authors: ['Author 1'],
      works: [],
      actors: [],
      tags: [],
      favorite: false,
      page_count: 30,
      views: '10',
      likes: '1',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
      cover_paths: ['/cover1.webp'],
      cached_pages: 0,
      cover_count: 1,
      last_page: 0, // unread
    },
    {
      source: 'jm',
      source_id: '102',
      display_id: '102',
      title: 'Recommend B',
      authors: ['Author 2'],
      works: [],
      actors: [],
      tags: [],
      favorite: false,
      page_count: 20,
      views: '20',
      likes: '2',
      uploaded_at: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
      cover_paths: ['/cover2.webp'],
      cached_pages: 5,
      cover_count: 1,
      last_page: 10, // in-progress
    },
  ]

  it('renders end title, recommendations and emits events correctly', async () => {
    const wrapper = mount(ReaderEndCard, {
      props: {
        recommendations: dummyRecs,
      },
    })

    // Defends against premature auto-completion bug: does NOT emit completed on mere mount
    expect(wrapper.emitted('completed')).toBeFalsy()

    // Title and seal
    expect(wrapper.text()).toContain('本子翻完了')
    expect(wrapper.text()).toContain('接卷阅览')

    // Recommendations count
    const cards = wrapper.findAll('.rec-card')
    expect(cards.length).toBe(2)
    expect(wrapper.text()).toContain('Recommend A')
    expect(wrapper.text()).toContain('Recommend B')

    // Status badges
    expect(wrapper.text()).toContain('未读')
    expect(wrapper.text()).toContain('在读 10P')

    // Click on recommendation card main triggers select
    const firstCardMain = wrapper.find('.rec-card-main')
    await firstCardMain.trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual(['jm', '101'])

    // Click on detail button triggers detail
    const firstDetailBtn = wrapper.find('.rec-detail-btn')
    await firstDetailBtn.trigger('click')
    expect(wrapper.emitted('detail')).toBeTruthy()
    expect(wrapper.emitted('detail')![0]).toEqual(['jm', '101'])

    // Click back to detail
    const backBtn = wrapper.find('.btn-primary')
    await backBtn.trigger('click')
    expect(wrapper.emitted('back')).toBeTruthy()

    // Click back to shelf
    const homeBtn = wrapper.find('.btn-ghost')
    await homeBtn.trigger('click')
    expect(wrapper.emitted('home')).toBeTruthy()
  })

  it('renders poetic empty note when recommendations are empty', () => {
    const wrapper = mount(ReaderEndCard, {
      props: {
        recommendations: [],
      },
    })
    expect(wrapper.text()).toContain('当前藏书均已翻阅完毕')
    expect(wrapper.find('.recommend-section').exists()).toBe(false)
  })
})

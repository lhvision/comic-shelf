import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { ref } from 'vue'
import { useChapterPageInfo } from '@/composables/useChapterPageInfo'
import type { Chapter, ComicDetail } from '@/types'

const pushMock = vi.fn<(url: string) => Promise<unknown>>()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}))

const switchActiveChapterMock =
  vi.fn<(source: string, sourceId: string, chapterId: string) => void>()
const goUpFromChapterMock = vi.fn<(source: string, sourceId: string) => void>()
vi.mock('@/composables/useHierarchicalNavigation', () => ({
  useHierarchicalNavigation: () => ({
    goToChapter: switchActiveChapterMock,
    goUpFromChapter: goUpFromChapterMock,
  }),
}))

describe('useChapterPageInfo.ts', () => {
  const chaptersData: Chapter[] = [
    { id: 'ch1', index: 1, title: '第一话', page_count: 10, start: 1 },
    { id: 'ch2', index: 2, title: '第二话', page_count: 15, start: 11 },
    { id: 'ch3', index: 3, title: '第三话', page_count: 20, start: 26 },
  ]

  const mockDetail = {
    source: 'jm',
    source_id: '123',
    title: '测试漫画',
    author: '测试作者',
    page_count: 45,
    cover_page: 1,
    cover_pages: [1],
    tags: [],
    from_cache: true,
    meta: {
      pages: [
        { index: 1, chapter: 'ch1', cached: true, file: '1.webp', ext: 'webp' },
        { index: 2, chapter: 'ch1', cached: true, file: '2.webp', ext: 'webp' },
        { index: 3, chapter: 'ch1', cached: false, file: '3.webp', ext: 'webp' },
        { index: 11, chapter: 'ch2', cached: true, file: '11.webp', ext: 'webp' },
        { index: 12, chapter: 'ch2', cached: false, file: '12.webp', ext: 'webp' },
      ],
      chapters: chaptersData,
    },
  } as unknown as ComicDetail

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('能准确定位 activeChapter、activeIndex 与前/后一话', () => {
    const source = ref('jm')
    const sourceId = ref('123')
    const chapterId = ref('ch2')
    const chapters = ref(chaptersData)
    const detail = ref(mockDetail)
    const progressEl = ref(0)

    const info = useChapterPageInfo({
      source,
      sourceId,
      chapterId,
      chapters,
      detail,
      progressEl,
    })

    expect(info.activeChapter.value?.id).toBe('ch2')
    expect(info.activeIndex.value).toBe(1)
    expect(info.prevChapter.value?.id).toBe('ch1')
    expect(info.nextChapter.value?.id).toBe('ch3')
    expect(info.chapterRange.value).toBe('第 11–25 全局页')
  })

  it('正确统计当前话的画页总数与已缓存数', () => {
    const source = ref('jm')
    const sourceId = ref('123')
    const chapterId = ref('ch1')
    const chapters = ref(chaptersData)
    const detail = ref(mockDetail)
    const progressEl = ref(0)

    const info = useChapterPageInfo({
      source,
      sourceId,
      chapterId,
      chapters,
      detail,
      progressEl,
    })

    expect(info.activeChapterTotal.value).toBe(10)
    // ch1 中 index 1, 2 cached=true, index 3 cached=false
    expect(info.activeChapterCached.value).toBe(2)
  })

  it('阅读进度在当前话区间时，计算相对页码并生成“继续阅读”文案', () => {
    const source = ref('jm')
    const sourceId = ref('123')
    const chapterId = ref('ch2') // start: 11, count: 15
    const chapters = ref(chaptersData)
    const detail = ref(mockDetail)
    const progressEl = ref(15) // 全局第 15 页，对应本话第 5 页 (15 - 11 + 1)

    const info = useChapterPageInfo({
      source,
      sourceId,
      chapterId,
      chapters,
      detail,
      progressEl,
    })

    expect(info.isCurrentChapterLastRead.value).toBe(true)
    expect(info.readChapterLabel.value).toBe('继续阅读 · 第 5 页')

    // 点击继续阅读，跳转至 progressEl 所在全局页码
    info.startReadingChapter()
    expect(pushMock).toHaveBeenCalledWith('/comic/jm/123/read/15?chapter=ch2')
  })

  it('阅读进度不在当前话时，文案为“开始阅读本话”并定位至首页', () => {
    const source = ref('jm')
    const sourceId = ref('123')
    const chapterId = ref('ch2') // start: 11
    const chapters = ref(chaptersData)
    const detail = ref(mockDetail)
    const progressEl = ref(2) // 还在 ch1

    const info = useChapterPageInfo({
      source,
      sourceId,
      chapterId,
      chapters,
      detail,
      progressEl,
    })

    expect(info.isCurrentChapterLastRead.value).toBe(false)
    expect(info.readChapterLabel.value).toBe('开始阅读本话')

    // 跳转至 ch2 起始页 11
    info.startReadingChapter()
    expect(pushMock).toHaveBeenCalledWith('/comic/jm/123/read/11?chapter=ch2')
  })

  it('goPrev 和 goNext 正确调度 goToChapter', () => {
    const source = ref('jm')
    const sourceId = ref('123')
    const chapterId = ref('ch2')
    const chapters = ref(chaptersData)
    const detail = ref(mockDetail)
    const progressEl = ref(0)

    const info = useChapterPageInfo({
      source,
      sourceId,
      chapterId,
      chapters,
      detail,
      progressEl,
    })

    info.goPrev()
    expect(switchActiveChapterMock).toHaveBeenCalledWith('jm', '123', 'ch1')

    info.goNext()
    expect(switchActiveChapterMock).toHaveBeenCalledWith('jm', '123', 'ch3')

    info.goToAlbum()
    expect(goUpFromChapterMock).toHaveBeenCalledWith('jm', '123')
  })
})

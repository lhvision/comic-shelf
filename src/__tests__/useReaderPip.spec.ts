import { effectScope, ref, type EffectScope } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { useReaderPip } from '@/composables/useReaderPip'
import ReaderPipWindow from '@/components/reader/ReaderPipWindow.vue'
import type { LibrarySummary } from '@/types'

interface MockPipWindow extends Window {
  __closeSpy: ReturnType<typeof vi.fn<() => void>>
  __dispatchPageHide?: () => void
}

function createMockPipWindow(): MockPipWindow {
  const doc = document.implementation.createHTMLDocument('pip')
  let pageHideListener: (() => void) | null = null
  const closeSpy = vi.fn<() => void>(() => {
    ;(mockWin as { closed: boolean }).closed = true
  })
  const mockWin = {
    document: doc,
    closed: false,
    focus: vi.fn<() => void>(),
    close: closeSpy,
    __closeSpy: closeSpy,
    addEventListener: vi.fn<(type: string, listener: EventListenerOrEventListenerObject) => void>(
      (type, listener) => {
        if (type === 'pagehide' && typeof listener === 'function') {
          pageHideListener = () => listener(new Event('pagehide'))
        }
      },
    ),
    removeEventListener: vi.fn<(type: string) => void>((type) => {
      if (type === 'pagehide') {
        pageHideListener = null
      }
    }),
    __dispatchPageHide: () => {
      pageHideListener?.()
    },
  } as unknown as MockPipWindow
  return mockWin
}

describe('useReaderPip', () => {
  let scope: EffectScope
  const originalIsSecureContext = window.isSecureContext
  const originalPip = window.documentPictureInPicture

  beforeEach(() => {
    scope = effectScope()
  })

  afterEach(() => {
    scope.stop()
    Object.defineProperty(window, 'isSecureContext', {
      configurable: true,
      value: originalIsSecureContext,
    })
    if (originalPip === undefined) {
      delete (window as { documentPictureInPicture?: DocumentPictureInPicture })
        .documentPictureInPicture
    } else {
      Object.defineProperty(window, 'documentPictureInPicture', {
        configurable: true,
        value: originalPip,
      })
    }
  })

  it('reports unsupported when documentPictureInPicture or secure context is missing', () => {
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false })
    scope.run(() => {
      const { isPipSupported } = useReaderPip()
      expect(isPipSupported.value).toBe(false)
    })
  })

  it('opens, handles external pagehide, and closes cleanly on scope dispose', async () => {
    const mockWin = createMockPipWindow()
    const requestWindow = vi.fn<() => Promise<Window>>().mockResolvedValue(mockWin)
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
    Object.defineProperty(window, 'documentPictureInPicture', {
      configurable: true,
      value: { window: null, requestWindow },
    })

    const isZoomed = ref(true)
    const onResetZoom = vi.fn<() => void>()
    const onClose = vi.fn<() => void>()

    await scope.run(async () => {
      const { isPipSupported, isPipOpen, pipMountTarget, openPip, closePip } = useReaderPip({
        isZoomed,
        onResetZoom,
        onClose,
      })

      expect(isPipSupported.value).toBe(true)
      const opened = await openPip('测试漫画')
      expect(opened).toBe(true)
      expect(onResetZoom).toHaveBeenCalledTimes(1)
      expect(isPipOpen.value).toBe(true)
      expect(pipMountTarget.value).toBeTruthy()
      expect(mockWin.document.title).toContain('测试漫画')

      // External close via browser PiP close control
      mockWin.__dispatchPageHide?.()
      expect(isPipOpen.value).toBe(false)
      expect(pipMountTarget.value).toBeNull()
      expect(onClose).toHaveBeenCalledTimes(1)

      // Re-open and close programmatically
      const mockWin2 = createMockPipWindow()
      requestWindow.mockResolvedValueOnce(mockWin2)
      await openPip('测试漫画')
      expect(isPipOpen.value).toBe(true)
      closePip()
      expect(mockWin2.__closeSpy).toHaveBeenCalledTimes(1)
      expect(isPipOpen.value).toBe(false)
      expect(onClose).toHaveBeenCalledTimes(2)
    })
  })

  it('closes active PiP window when scope disposes (route leave)', async () => {
    const mockWin = createMockPipWindow()
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
    Object.defineProperty(window, 'documentPictureInPicture', {
      configurable: true,
      value: {
        window: null,
        requestWindow: vi.fn<() => Promise<Window>>().mockResolvedValue(mockWin),
      },
    })

    await scope.run(async () => {
      const { openPip, isPipOpen } = useReaderPip()
      await openPip('离场清理')
      expect(isPipOpen.value).toBe(true)
    })

    scope.stop()
    expect(mockWin.__closeSpy).toHaveBeenCalledTimes(1)
  })

  it('deduplicates concurrent openPip calls while requestWindow is pending', async () => {
    const mockWin = createMockPipWindow()
    let resolveReq: ((win: Window) => void) | null = null
    const requestWindow = vi.fn<() => Promise<Window>>(
      () =>
        new Promise<Window>((resolve) => {
          resolveReq = resolve
        }),
    )
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
    Object.defineProperty(window, 'documentPictureInPicture', {
      configurable: true,
      value: { window: null, requestWindow },
    })

    await scope.run(async () => {
      const { openPip, isPipOpen } = useReaderPip()
      const first = openPip('防抖连击')
      const second = openPip('防抖连击')
      expect(requestWindow).toHaveBeenCalledTimes(1)
      resolveReq?.(mockWin)
      const [r1, r2] = await Promise.all([first, second])
      expect(r1).toBe(true)
      expect(r2).toBe(true)
      expect(isPipOpen.value).toBe(true)
    })
  })
})

describe('ReaderPipWindow', () => {
  it('teleports reader stage into mountTarget and emits prev/next/close respecting RTL', async () => {
    const targetDoc = document.implementation.createHTMLDocument('pip-host')
    const mountTarget = targetDoc.createElement('div')
    targetDoc.body.appendChild(mountTarget)

    const wrapper = mount(ReaderPipWindow, {
      props: {
        open: true,
        mountTarget,
        title: '测试单本',
        chapterLabel: '第 1 話',
        pageSrc: '/api/library/jm/1/pages/5/file',
        currentLocalPage: 5,
        total: 20,
        canPrev: true,
        canNext: true,
        rtlHorizontal: true,
        prevIcon: 'arrow-left',
        nextIcon: 'arrow-right',
      },
    })

    const img = mountTarget.querySelector('img')
    expect(img?.getAttribute('src')).toBe('/api/library/jm/1/pages/5/file')
    expect(mountTarget.querySelector('.pip-reader-counter')?.textContent).toBe('5 / 20')

    // In RTL mode, left tap zone advances to next page, right tap zone goes to prev page
    ;(mountTarget.querySelector('.pip-tap-zone.is-left') as HTMLButtonElement).click()
    ;(mountTarget.querySelector('.pip-tap-zone.is-right') as HTMLButtonElement).click()
    expect(wrapper.emitted('next')?.length).toBe(1)
    expect(wrapper.emitted('prev')?.length).toBe(1)

    const buttons = mountTarget.querySelectorAll('header button')
    ;(buttons[0] as HTMLButtonElement).click()
    expect(wrapper.emitted('close')?.length).toBe(1)

    wrapper.unmount()
  })

  it('supports chapter switching, quick book switching with status sorting, end-card recommendations, and direct-pass isolation', async () => {
    const targetDoc = document.implementation.createHTMLDocument('pip-host-2')
    const mountTarget = targetDoc.createElement('div')
    targetDoc.body.appendChild(mountTarget)

    const sampleBooks: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: 'current-1',
        display_id: 'JM1',
        title: '当前正在看的作品',
        page_count: 10,
        authors: ['作者A'],
        works: [],
        actors: [],
        tags: [],
        favorite: false,
        views: '',
        likes: '',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-11-01T00:00:00Z',
        cover_paths: [],
        cached_pages: 10,
        cover_count: 1,
        last_page: 5,
      },
      {
        source: 'jm',
        source_id: 'done-2',
        display_id: 'JM2',
        title: '已读完的漫画',
        page_count: 20,
        authors: ['作者B'],
        works: [],
        actors: [],
        tags: [],
        favorite: false,
        views: '',
        likes: '',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-11-05T00:00:00Z',
        cover_paths: [],
        cached_pages: 20,
        cover_count: 1,
        last_page: 20,
      },
      {
        source: 'jm',
        source_id: 'reading-3',
        display_id: 'JM3',
        title: '在读中的漫画',
        page_count: 30,
        authors: ['作者C'],
        works: [],
        actors: [],
        tags: [],
        favorite: false,
        views: '',
        likes: '',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '2026-11-03T00:00:00Z',
        cover_paths: [],
        cached_pages: 30,
        cover_count: 1,
        last_page: 12,
      },
    ]

    const chapters = [
      { id: 'c1', index: 1, title: '序章', start: 1, page_count: 5 },
      { id: 'c2', index: 2, title: '正篇', start: 6, page_count: 5 },
    ]

    const wrapper = mount(ReaderPipWindow, {
      props: {
        open: true,
        mountTarget,
        endOpen: false,
        atFinalPage: true,
        title: '当前正在看的作品',
        chapterLabel: '第 1 話 · 序章',
        chapters,
        currentChapterId: 'c1',
        currentSource: 'jm',
        currentSourceId: 'current-1',
        pageSrc: '/api/library/jm/current-1/pages/5/file',
        currentLocalPage: 5,
        total: 5,
        canPrev: true,
        canNext: true,
        rtlHorizontal: false,
        prevIcon: 'arrow-left',
        nextIcon: 'arrow-right',
        recommendations: [sampleBooks[2]!],
        libraryItems: sampleBooks,
        isDirectPass: false,
      },
    })

    // Open chapters drawer & pick chapter 2
    const chapterTrigger = mountTarget.querySelector(
      'button[title="选择本话章节"]',
    ) as HTMLButtonElement
    chapterTrigger.click()
    await wrapper.vm.$nextTick()
    const chapterItems = mountTarget.querySelectorAll('.pip-chapter-item')
    expect(chapterItems.length).toBe(2)
    ;(chapterItems[1] as HTMLButtonElement).click()
    expect(wrapper.emitted('selectChapter')?.[0]).toEqual(['c2'])

    // Open books drawer: current comic excluded, in-progress comes before completed
    const booksTrigger = mountTarget.querySelector(
      'button[title="快捷切换书库作品"]',
    ) as HTMLButtonElement
    booksTrigger.click()
    await wrapper.vm.$nextTick()
    const bookTitles = Array.from(mountTarget.querySelectorAll('.pip-book-title')).map(
      (el) => el.textContent,
    )
    expect(bookTitles).toEqual(['在读中的漫画', '已读完的漫画'])

    // Escape closes drawer first without closing PiP
    targetDoc.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()
    expect(mountTarget.querySelector('.pip-switcher-panel')).toBeNull()
    expect(wrapper.emitted('close')).toBeFalsy()

    // Entering endOpen triggers completed and shows recommendations + restart
    await wrapper.setProps({ endOpen: true } as Record<string, unknown>)
    expect(wrapper.emitted('completed')?.length).toBe(1)
    expect(mountTarget.querySelector('.pip-end-view')).toBeTruthy()
    expect(mountTarget.querySelector('.pip-rec-list .pip-book-title')?.textContent).toBe(
      '在读中的漫画',
    )
    const restartBtn = Array.from(mountTarget.querySelectorAll('.pip-end-actions button')).find(
      (b) => b.textContent?.includes('再看一遍'),
    ) as HTMLButtonElement
    restartBtn.click()
    expect(wrapper.emitted('restart')?.length).toBe(1)

    // Direct Pass hides switcher and recommendations while keeping chapters
    await wrapper.setProps({ isDirectPass: true } as Record<string, unknown>)
    expect(mountTarget.querySelector('button[title="快捷切换书库作品"]')).toBeNull()
    expect(mountTarget.querySelector('button[title="选择本话章节"]')).toBeTruthy()
    expect(mountTarget.querySelector('.pip-rec-list')).toBeNull()

    wrapper.unmount()
  })
})

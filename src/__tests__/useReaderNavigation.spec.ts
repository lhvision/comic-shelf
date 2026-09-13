import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { ref, reactive, computed, type Ref } from 'vue'
import {
  useReaderNavigation,
  type UseReaderNavigationOptions,
} from '@/composables/useReaderNavigation'
import { DEFAULT_SETTINGS, type ReaderSettings } from '@/composables/useReaderSettings'
import type { Router } from 'vue-router'

describe('useReaderNavigation - Discrete Wheel Stepping & Dual-Axis Discrimination', () => {
  let settings: ReaderSettings
  let scrollEl: Ref<HTMLElement | null>
  let currentPage: Ref<number>
  let currentGroupIndex: Ref<number>
  let showChromeTemporarily: () => void
  let resetAutoTurnCountdown: () => void
  let mockScrollTo: (_options?: ScrollToOptions | number, _y?: number) => void
  let mockContainer: HTMLElement

  beforeEach(() => {
    vi.useFakeTimers()
    settings = reactive<ReaderSettings>({
      ...DEFAULT_SETTINGS,
      mode: 'horizontal',
      pagesPerView: 2,
      direction: 'ltr',
    })

    currentPage = ref<number>(1)
    currentGroupIndex = ref<number>(0)
    showChromeTemporarily = vi.fn<() => void>()
    resetAutoTurnCountdown = vi.fn<() => void>()

    mockScrollTo = vi.fn<(_options?: ScrollToOptions | number, _y?: number) => void>()
    mockContainer = document.createElement('main')
    mockContainer.scrollTo = mockScrollTo as unknown as typeof mockContainer.scrollTo

    // Create 3 mock spread sections with data-group-index
    for (let i = 0; i < 3; i += 1) {
      const spread = document.createElement('section')
      spread.dataset.groupIndex = String(i)
      Object.defineProperty(spread, 'offsetLeft', { value: i * 800, configurable: true })
      mockContainer.appendChild(spread)
    }

    scrollEl = ref<HTMLElement | null>(mockContainer)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function createNavigation(overrides?: Partial<UseReaderNavigationOptions>) {
    const pageGroups = computed(() => [
      [1, 2],
      [3, 4],
      [5, 6],
    ])
    const lastGroupIndex = computed(() => 2)
    const mockRouter = {
      replace: vi.fn<(_url: string) => Promise<void>>(),
      push: vi.fn<(_url: string) => Promise<void>>(),
    } as unknown as Router

    return useReaderNavigation({
      scrollEl,
      settings,
      currentPage,
      currentGroupIndex,
      pageGroups,
      lastGroupIndex,
      clampToScope: (p: number) => Math.min(Math.max(p, 1), 6),
      groupIndexForPage: (p: number) => Math.floor((p - 1) / 2),
      groupFirstPage: (g: number) => g * 2 + 1,
      showChromeTemporarily,
      resetAutoTurnCountdown,
      source: computed(() => 'jm'),
      sourceId: computed(() => 'test-comic'),
      nextChapter: computed(() => null),
      prevChapter: computed(() => null),
      scopeId: ref(null),
      router: mockRouter,
      ...overrides,
    })
  }

  it('ignores onWheel when reader is not in horizontal mode', () => {
    settings.mode = 'vertical-continuous'
    const nav = createNavigation()

    const preventDefault = vi.fn<() => void>()
    const event = new WheelEvent('wheel', {
      deltaY: 100,
      deltaX: 0,
      cancelable: true,
    })
    Object.defineProperty(event, 'preventDefault', { value: preventDefault })

    nav.onWheel(event)

    expect(preventDefault).not.toHaveBeenCalled()
    expect(currentGroupIndex.value).toBe(0)
    expect(mockScrollTo).not.toHaveBeenCalled()
  })

  it('passes through horizontal gestures (|deltaX| > |deltaY|) for native trackpad smooth scrolling', () => {
    const nav = createNavigation()

    const preventDefault = vi.fn<() => void>()
    const event = new WheelEvent('wheel', {
      deltaX: 50,
      deltaY: 10,
      cancelable: true,
    })
    Object.defineProperty(event, 'preventDefault', { value: preventDefault })

    nav.onWheel(event)

    expect(preventDefault).not.toHaveBeenCalled()
    expect(currentGroupIndex.value).toBe(0)
    expect(mockScrollTo).not.toHaveBeenCalled()
  })

  it('intercepts vertical wheel (|deltaY| >= 40) and steps to next group with smooth scrollTo', () => {
    const nav = createNavigation()

    const preventDefault = vi.fn<() => void>()
    const event = new WheelEvent('wheel', {
      deltaX: 0,
      deltaY: 100,
      cancelable: true,
    })
    Object.defineProperty(event, 'preventDefault', { value: preventDefault })

    nav.onWheel(event)

    expect(preventDefault).toHaveBeenCalled()
    expect(currentGroupIndex.value).toBe(1)
    expect(currentPage.value).toBe(3) // group 1 starts at page 3
    expect(mockScrollTo).toHaveBeenCalledWith({ left: 800, top: 0, behavior: 'smooth' })
    expect(showChromeTemporarily).toHaveBeenCalled()
    expect(resetAutoTurnCountdown).toHaveBeenCalled()
  })

  it('intercepts negative vertical wheel and steps to previous group', () => {
    currentGroupIndex.value = 1
    currentPage.value = 3
    const nav = createNavigation()

    const preventDefault = vi.fn<() => void>()
    const event = new WheelEvent('wheel', {
      deltaX: 0,
      deltaY: -100,
      cancelable: true,
    })
    Object.defineProperty(event, 'preventDefault', { value: preventDefault })

    nav.onWheel(event)

    expect(preventDefault).toHaveBeenCalled()
    expect(currentGroupIndex.value).toBe(0)
    expect(currentPage.value).toBe(1)
    expect(mockScrollTo).toHaveBeenCalledWith({ left: 0, top: 0, behavior: 'smooth' })
  })

  it('throttles rapid consecutive wheel spins within cooldown period', () => {
    const nav = createNavigation()

    const event1 = new WheelEvent('wheel', { deltaY: 100, cancelable: true })
    const event2 = new WheelEvent('wheel', { deltaY: 100, cancelable: true })
    const preventDefault = vi.fn<() => void>()
    Object.defineProperty(event1, 'preventDefault', { value: preventDefault })
    Object.defineProperty(event2, 'preventDefault', { value: preventDefault })

    nav.onWheel(event1)
    expect(currentGroupIndex.value).toBe(1)

    // Rapid second spin during 220ms cooldown
    nav.onWheel(event2)
    expect(currentGroupIndex.value).toBe(1) // Still at 1, prevented runaway flips

    // Fast-forward beyond 220ms
    vi.advanceTimersByTime(230)

    const event3 = new WheelEvent('wheel', { deltaY: 100, cancelable: true })
    Object.defineProperty(event3, 'preventDefault', { value: preventDefault })
    nav.onWheel(event3)
    expect(currentGroupIndex.value).toBe(2)
  })

  it('accumulates sub-threshold wheel deltas before triggering step', () => {
    const nav = createNavigation()

    const preventDefault = vi.fn<() => void>()
    const makeEvent = (dy: number) => {
      const ev = new WheelEvent('wheel', { deltaY: dy, cancelable: true })
      Object.defineProperty(ev, 'preventDefault', { value: preventDefault })
      return ev
    }

    // Two small 15px micro-scrolls (total 30 < 40)
    nav.onWheel(makeEvent(15))
    nav.onWheel(makeEvent(15))
    expect(currentGroupIndex.value).toBe(0)

    // Third micro-scroll puts total at 45 >= 40
    nav.onWheel(makeEvent(15))
    expect(currentGroupIndex.value).toBe(1)
  })

  it('clears accumulated sub-threshold delta after 150ms inactivity', () => {
    const nav = createNavigation()

    const preventDefault = vi.fn<() => void>()
    const makeEvent = (dy: number) => {
      const ev = new WheelEvent('wheel', { deltaY: dy, cancelable: true })
      Object.defineProperty(ev, 'preventDefault', { value: preventDefault })
      return ev
    }

    nav.onWheel(makeEvent(20))
    expect(currentGroupIndex.value).toBe(0)

    // Inactivity timeout
    vi.advanceTimersByTime(160)

    // Another 20 should not trigger because previous 20 was cleared
    nav.onWheel(makeEvent(20))
    expect(currentGroupIndex.value).toBe(0)
  })

  it('steps smoothly in RTL mode when rolling wheel down (nextGroup)', () => {
    settings.direction = 'rtl'
    // In RTL, group 0 is on the right (1600px), group 1 is at 800px, group 2 is at 0px
    mockContainer.innerHTML = ''
    for (let i = 0; i < 3; i += 1) {
      const spread = document.createElement('section')
      spread.dataset.groupIndex = String(i)
      Object.defineProperty(spread, 'offsetLeft', { value: (2 - i) * 800, configurable: true })
      mockContainer.appendChild(spread)
    }

    const nav = createNavigation()
    const preventDefault = vi.fn<() => void>()
    const event = new WheelEvent('wheel', { deltaY: 100, cancelable: true })
    Object.defineProperty(event, 'preventDefault', { value: preventDefault })

    nav.onWheel(event)

    expect(preventDefault).toHaveBeenCalled()
    expect(currentGroupIndex.value).toBe(1)
    expect(mockScrollTo).toHaveBeenCalledWith({ left: 800, top: 0, behavior: 'smooth' })
  })

  it('bypasses wheel interception when Ctrl or Meta key is pressed (browser zoom)', () => {
    const nav = createNavigation()
    const preventDefault = vi.fn<() => void>()

    const ctrlEvent = new WheelEvent('wheel', { deltaY: 100, ctrlKey: true, cancelable: true })
    Object.defineProperty(ctrlEvent, 'preventDefault', { value: preventDefault })
    nav.onWheel(ctrlEvent)

    const metaEvent = new WheelEvent('wheel', { deltaY: 100, metaKey: true, cancelable: true })
    Object.defineProperty(metaEvent, 'preventDefault', { value: preventDefault })
    nav.onWheel(metaEvent)

    expect(preventDefault).not.toHaveBeenCalled()
    expect(currentGroupIndex.value).toBe(0)
  })

  it('clamps to lastGroupIndex and final page when scrolled near bottom in vertical-continuous mode', () => {
    settings.mode = 'vertical-continuous'
    const nav = createNavigation()

    // Mock container layout: clientHeight=800, scrollHeight=2400 (max=1600)
    Object.defineProperty(mockContainer, 'clientHeight', { value: 800, configurable: true })
    Object.defineProperty(mockContainer, 'scrollHeight', { value: 2400, configurable: true })
    Object.defineProperty(mockContainer, 'scrollTop', { value: 1590, configurable: true }) // max - 10

    // Mock spreads with vertical offsetTop and offsetHeight
    const spreads = mockContainer.querySelectorAll('section')
    spreads.forEach((spread, idx) => {
      Object.defineProperty(spread, 'offsetTop', { value: idx * 800, configurable: true })
      Object.defineProperty(spread, 'offsetHeight', { value: 800, configurable: true })
    })

    nav.onScroll()
    // Trigger requestAnimationFrame
    vi.runAllTimers()

    expect(currentGroupIndex.value).toBe(2)
    expect(currentPage.value).toBe(5) // groupFirstPage(2) is 2*2+1 = 5
  })

  it('detects spread via readLine (40% viewport) in vertical-continuous mode', () => {
    settings.mode = 'vertical-continuous'
    const nav = createNavigation()

    Object.defineProperty(mockContainer, 'clientHeight', { value: 1000, configurable: true })
    Object.defineProperty(mockContainer, 'scrollHeight', { value: 3000, configurable: true })
    Object.defineProperty(mockContainer, 'scrollTop', { value: 650, configurable: true })
    // readLine = 650 + 1000 * 0.4 = 1050

    const spreads = mockContainer.querySelectorAll('section')
    spreads.forEach((spread, idx) => {
      Object.defineProperty(spread, 'offsetTop', { value: idx * 900, configurable: true })
      Object.defineProperty(spread, 'offsetHeight', { value: 900, configurable: true })
    })
    // Group 0: 0..900, Group 1: 900..1800 (contains 1050!), Group 2: 1800..2700

    nav.onScroll()
    vi.runAllTimers()

    expect(currentGroupIndex.value).toBe(1)
    expect(currentPage.value).toBe(3)
  })

  it('does not invoke resetAutoTurnCountdown on scroll in vertical-continuous mode', () => {
    settings.mode = 'vertical-continuous'
    const nav = createNavigation()

    nav.onScroll()
    vi.runAllTimers()

    expect(resetAutoTurnCountdown).not.toHaveBeenCalled()
  })

  it('invokes resetAutoTurnCountdown on scroll in paged mode', () => {
    settings.mode = 'vertical-paged'
    const nav = createNavigation()

    nav.onScroll()
    vi.runAllTimers()

    expect(resetAutoTurnCountdown).toHaveBeenCalled()
  })

  it('efficiently resolves group index on large scale (100+ groups) without full scanning', () => {
    settings.mode = 'vertical-continuous'
    mockContainer.innerHTML = ''
    const totalGroups = 120
    const groupHeight = 800

    for (let i = 0; i < totalGroups; i += 1) {
      const spread = document.createElement('section')
      spread.dataset.groupIndex = String(i)
      Object.defineProperty(spread, 'offsetTop', { value: i * groupHeight, configurable: true })
      Object.defineProperty(spread, 'offsetHeight', { value: groupHeight, configurable: true })
      mockContainer.appendChild(spread)
    }

    Object.defineProperty(mockContainer, 'clientHeight', { value: 1000, configurable: true })
    Object.defineProperty(mockContainer, 'scrollHeight', {
      value: totalGroups * groupHeight,
      configurable: true,
    })
    // Jump to group 75: scrollTop such that readLine is within group 75 (75 * 800 = 60000)
    // readLine = position + 1000 * 0.4 = position + 400. Let position = 60200 -> readLine = 60600 (in [60000, 60800])
    Object.defineProperty(mockContainer, 'scrollTop', { value: 60200, configurable: true })

    const pageGroups = computed(() => Array.from({ length: totalGroups }, (_, i) => [i + 1]))
    const lastGroupIndex = computed(() => totalGroups - 1)

    const nav = useReaderNavigation({
      scrollEl,
      settings,
      currentPage,
      currentGroupIndex,
      pageGroups,
      lastGroupIndex,
      clampToScope: (p: number) => p,
      groupIndexForPage: (p: number) => p - 1,
      groupFirstPage: (g: number) => g + 1,
      showChromeTemporarily,
      resetAutoTurnCountdown,
      source: computed(() => 'jm'),
      sourceId: computed(() => 'test-large'),
      nextChapter: computed(() => null),
      prevChapter: computed(() => null),
      scopeId: ref(null),
      router: {
        replace: vi.fn<(_url: string) => Promise<void>>(),
        push: vi.fn<(_url: string) => Promise<void>>(),
      } as unknown as Router,
    })

    nav.onScroll()
    vi.runAllTimers()

    expect(currentGroupIndex.value).toBe(75)
    expect(currentPage.value).toBe(76)
  })

  it('accurately resolves group index when jumping 2 groups in flip mode', () => {
    settings.mode = 'horizontal'
    const nav = createNavigation()

    // Container width 800. Group 0 at 0, Group 1 at 800, Group 2 at 1600.
    // User rapidly scrolls to group 2 (position 1600).
    mockContainer.scrollLeft = 1600
    nav.onScroll()
    vi.runAllTimers()

    expect(currentGroupIndex.value).toBe(2)
    expect(currentPage.value).toBe(5)
  })

  it('pre-warms the first pages of nextChapter when reaching chapter end', () => {
    const createdImages: string[] = []
    const OriginalImage = globalThis.Image
    class MockImage {
      set src(val: string) {
        createdImages.push(val)
      }
    }
    globalThis.Image = MockImage as unknown as typeof Image

    try {
      const nextChapterRef = computed(() => ({
        id: 'ch2',
        index: 2,
        title: '第 2 话',
        page_count: 10,
        start: 7,
      }))
      const nav = createNavigation({ nextChapter: nextChapterRef })

      // Preload around group 2 (pages 5-6, the last group in a 6-page chapter)
      void nav.preloadAround(5)
      vi.runAllTimers()

      // Should have preloaded pages including nextChapter's start pages (7, 8)
      expect(createdImages.some((url) => url.includes('/pages/7/file'))).toBe(true)
      expect(createdImages.some((url) => url.includes('/pages/8/file'))).toBe(true)
    } finally {
      globalThis.Image = OriginalImage
    }
  })
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ChapterSwitcher from '@/components/detail/ChapterSwitcher.vue'
import type { Chapter } from '@/types'

function makeChapters(count: number): Chapter[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `chap_${i + 1}`,
    index: i + 1,
    title: `第 ${i + 1} 话`,
    start: i * 20 + 1,
    page_count: 20,
    cover_path: `/cover_${i + 1}.webp`,
  }))
}

describe('ChapterSwitcher', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['requestAnimationFrame'] })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('renders nothing when chapters has 1 or fewer elements', () => {
    const singleWrapper = mount(ChapterSwitcher, {
      props: {
        chapters: makeChapters(1),
        activeId: 'chap_1',
      },
    })
    expect(singleWrapper.find('.chapter-switcher').exists()).toBe(false)

    const emptyWrapper = mount(ChapterSwitcher, {
      props: {
        chapters: [],
        activeId: null,
      },
    })
    expect(emptyWrapper.find('.chapter-switcher').exists()).toBe(false)
  })

  it('renders all chapter buttons with correct active state when chapters > 1', () => {
    const chapters = makeChapters(5)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_3',
      },
    })

    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(5)

    // Check 3rd chapter is active
    const activeBtn = buttons[2]!
    expect(activeBtn.attributes('aria-pressed')).toBe('true')
    expect(activeBtn.attributes('data-active')).toBe('true')
    expect(activeBtn.attributes('data-state')).toBe('active')
    expect(activeBtn.find('.chapter-current').text()).toBe('当前')

    // Past chapters (1, 2)
    expect(buttons[0]!.attributes('data-state')).toBe('past')
    expect(buttons[1]!.attributes('data-state')).toBe('past')

    // Upcoming chapters (4, 5)
    expect(buttons[3]!.attributes('data-state')).toBe('upcoming')
    expect(buttons[4]!.attributes('data-state')).toBe('upcoming')
  })

  it('emits change event when clicking a chapter button', async () => {
    const chapters = makeChapters(5)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_1',
      },
    })

    const buttons = wrapper.findAll('button')
    await buttons[3]!.trigger('click')

    expect(wrapper.emitted('change')).toBeTruthy()
    expect(wrapper.emitted('change')?.[0]).toEqual(['chap_4'])
  })

  it('navigates with ArrowRight, ArrowLeft, Home, and End keys', async () => {
    const chapters = makeChapters(10)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_5',
      },
      attachTo: document.body,
    })

    await nextTick()
    const switcher = wrapper.find('.chapter-switcher')

    // ArrowRight -> chap_6
    await switcher.trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('change')?.[0]).toEqual(['chap_6'])

    // ArrowLeft -> chap_4
    await switcher.trigger('keydown', { key: 'ArrowLeft' })
    expect(wrapper.emitted('change')?.[1]).toEqual(['chap_4'])

    // Home -> chap_1
    await switcher.trigger('keydown', { key: 'Home' })
    expect(wrapper.emitted('change')?.[2]).toEqual(['chap_1'])

    // End -> chap_10
    await switcher.trigger('keydown', { key: 'End' })
    expect(wrapper.emitted('change')?.[3]).toEqual(['chap_10'])

    wrapper.unmount()
  })

  it('calculates center position and triggers initial alignment on mount', async () => {
    const chapters = makeChapters(50)
    const scrollToSpy = vi.fn<(options?: ScrollToOptions | number) => void>()
    HTMLElement.prototype.scrollTo = scrollToSpy

    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_45',
      },
      attachTo: document.body,
    })

    const container = wrapper.find('.chapter-switcher').element as HTMLElement
    // Mock dimensions for container
    Object.defineProperty(container, 'clientWidth', { value: 600, configurable: true })
    Object.defineProperty(container, 'scrollWidth', { value: 5000, configurable: true })
    Object.defineProperty(container, 'scrollLeft', { value: 0, writable: true, configurable: true })
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue({
      left: 100,
      right: 700,
      top: 0,
      bottom: 50,
      width: 600,
      height: 50,
      x: 100,
      y: 0,
      toJSON: () => {},
    })

    // Mock active element dimensions
    const activeBtn = wrapper.find('button[data-active="true"]').element as HTMLElement
    Object.defineProperty(activeBtn, 'offsetWidth', { value: 120, configurable: true })
    vi.spyOn(activeBtn, 'getBoundingClientRect').mockReturnValue({
      left: 2000,
      right: 2120,
      top: 0,
      bottom: 50,
      width: 120,
      height: 50,
      x: 2000,
      y: 0,
      toJSON: () => {},
    })

    await nextTick()
    vi.runAllTimers()

    // TargetLeft = 0 + (2000 - 100) - (600 - 120) / 2 = 1900 - 240 = 1660
    expect(scrollToSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        left: 1660,
        behavior: 'auto',
      }),
    )

    scrollToSpy.mockClear()

    // When activeId changes dynamically after mount, it uses smooth scroll
    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({
      activeId: 'chap_46',
    })
    const nextBtn = wrapper.find('button[data-active="true"]').element as HTMLElement
    Object.defineProperty(nextBtn, 'offsetWidth', { value: 120, configurable: true })
    vi.spyOn(nextBtn, 'getBoundingClientRect').mockReturnValue({
      left: 2150,
      right: 2270,
      top: 0,
      bottom: 50,
      width: 120,
      height: 50,
      x: 2150,
      y: 0,
      toJSON: () => {},
    })

    await nextTick()
    vi.runAllTimers()

    expect(scrollToSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        behavior: 'smooth',
        left: 1810,
      }),
    )

    delete (HTMLElement.prototype as Partial<HTMLElement>).scrollTo
    wrapper.unmount()
  })

  it('windows 1000 chapters around activeId with O(1) chip count and accurate states', () => {
    const chapters = makeChapters(1000)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_500',
      },
    })

    const chips = wrapper.findAll('button.chapter-chip')
    expect(chips.length).toBe(33)

    const activeBtn = wrapper.find('button.chapter-chip[data-active="true"]')
    expect(activeBtn.attributes('data-state')).toBe('active')
    expect(activeBtn.find('.chapter-ordinal').text()).toBe('500')

    // First chip in window (484) is past, last chip in window (516) is upcoming
    expect(chips[0]!.find('.chapter-ordinal').text()).toBe('484')
    expect(chips[0]!.attributes('data-state')).toBe('past')
    expect(chips[chips.length - 1]!.find('.chapter-ordinal').text()).toBe('516')
    expect(chips[chips.length - 1]!.attributes('data-state')).toBe('upcoming')

    const edgeButtons = wrapper.findAll('button.chapter-edge-jump')
    expect(edgeButtons.length).toBe(2)
    expect(wrapper.find('.chapter-jump-trigger').text()).toContain('500/1000')
  })

  it('slides window when navigating Home and End on 1000 chapters', async () => {
    const chapters = makeChapters(1000)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_500',
      },
      attachTo: document.body,
    })

    await nextTick()
    const switcher = wrapper.find('.chapter-switcher')
    await switcher.trigger('keydown', { key: 'Home' })
    expect(wrapper.emitted('change')?.[0]).toEqual(['chap_1'])

    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({ activeId: 'chap_1' })
    await nextTick()

    const startChips = wrapper.findAll('button.chapter-chip')
    expect(startChips.length).toBe(33)
    expect(startChips[0]!.find('.chapter-ordinal').text()).toBe('1')
    expect(wrapper.findAll('button.chapter-edge-jump').length).toBe(1)

    await switcher.trigger('keydown', { key: 'End' })
    expect(wrapper.emitted('change')?.[1]).toEqual(['chap_1000'])

    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({ activeId: 'chap_1000' })
    await nextTick()

    const endChips = wrapper.findAll('button.chapter-chip')
    expect(endChips.length).toBe(33)
    expect(endChips[endChips.length - 1]!.find('.chapter-ordinal').text()).toBe('1000')
    expect(wrapper.findAll('button.chapter-edge-jump').length).toBe(1)

    wrapper.unmount()
  })

  it('opens quick jump popover, caps rendered items at 40, and jumps on Enter', async () => {
    const chapters = makeChapters(1000)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_12',
      },
      attachTo: document.body,
    })

    await wrapper.find('.chapter-jump-trigger').trigger('click')
    await nextTick()

    // Segment view initially renders <= 40 items
    expect(wrapper.findAll('.chapter-jump-item').length).toBe(40)

    const input = wrapper.find('.chapter-jump-input')
    // Broad match still capped at 40 items
    await input.setValue('第')
    expect(wrapper.findAll('.chapter-jump-item').length).toBe(40)
    expect(wrapper.find('.chapter-jump-note').text()).toContain('仅显示前 40 条')

    // Exact chapter number query puts 680 first and Enter emits change
    await input.setValue('680')
    const matchedItems = wrapper.findAll('.chapter-jump-item')
    expect(matchedItems[0]!.find('.chapter-jump-idx').text()).toBe('680')

    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('change')?.[0]).toEqual(['chap_680'])

    wrapper.unmount()
  })

  it('opens jump popover on first segment when clicking left edge ellipsis button', async () => {
    const chapters = makeChapters(1000)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_500',
      },
      attachTo: document.body,
    })

    const leftEdgeBtn = wrapper.findAll('button.chapter-edge-jump')[0]!
    await leftEdgeBtn.trigger('click')
    await nextTick()

    const firstSegmentTab = wrapper.findAll('.chapter-segment-btn')[0]!
    expect(firstSegmentTab.attributes('aria-selected')).toBe('true')
    expect(wrapper.findAll('.chapter-jump-item')[0]!.find('.chapter-jump-idx').text()).toBe('1')

    wrapper.unmount()
  })

  it('retains keyboard focus with preventScroll after windowed async activeId update', async () => {
    const chapters = makeChapters(1000)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_500',
      },
      attachTo: document.body,
    })

    await nextTick()
    const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
    const initialActiveBtn = wrapper.find('button.chapter-chip[data-active="true"]')
      .element as HTMLElement
    initialActiveBtn.focus()

    await wrapper.find('.chapter-switcher').trigger('keydown', { key: 'End' })
    expect(wrapper.emitted('change')?.[0]).toEqual(['chap_1000'])

    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({ activeId: 'chap_1000' })
    await nextTick()

    const activeBtn = wrapper.find('button.chapter-chip[data-active="true"]').element as HTMLElement
    expect(document.activeElement).toBe(activeBtn)
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true })

    // External navigation to another id clears stale pendingFocusId
    focusSpy.mockClear()
    await wrapper.find('.chapter-switcher').trigger('keydown', { key: 'Home' })
    expect(wrapper.emitted('change')?.[1]).toEqual(['chap_1'])
    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({ activeId: 'chap_999' })
    await nextTick()
    expect(focusSpy).not.toHaveBeenCalled()
    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({ activeId: 'chap_1' })
    await nextTick()
    expect(focusSpy).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('cancels pending requestAnimationFrame on rapid changes and unmount', async () => {
    const chapters = makeChapters(10)
    const cancelSpy = vi.spyOn(globalThis, 'cancelAnimationFrame')
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_1',
      },
      attachTo: document.body,
    })

    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({ activeId: 'chap_2' })
    await nextTick()
    await (
      wrapper as unknown as { setProps: (p: Record<string, unknown>) => Promise<void> }
    ).setProps({ activeId: 'chap_3' })
    await nextTick()

    expect(cancelSpy).toHaveBeenCalled()
    cancelSpy.mockClear()

    wrapper.unmount()
    expect(cancelSpy).toHaveBeenCalled()
  })

  it('opens tail segment from right edge jump near segment boundary', async () => {
    const chapters = makeChapters(1000)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_95',
      },
      attachTo: document.body,
    })

    const rightEdgeBtn = wrapper.find('button.chapter-edge-jump--end')
    expect(rightEdgeBtn.text()).toContain('112–1000')
    await rightEdgeBtn.trigger('click')
    await nextTick()

    const segmentTabs = wrapper.findAll('.chapter-segment-btn')
    expect(segmentTabs[1]!.attributes('aria-selected')).toBe('true')
    expect(wrapper.findAll('.chapter-jump-item')[0]!.find('.chapter-jump-idx').text()).toBe('101')

    wrapper.unmount()
  })

  it('supports segment switching, expanding all 100 items, empty state, and click selection', async () => {
    const chapters = makeChapters(1000)
    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_12',
      },
      attachTo: document.body,
    })

    await wrapper.find('.chapter-jump-trigger').trigger('click')
    await nextTick()

    // Switch to 3rd segment (201-300) and expand full 100 items
    await wrapper.findAll('.chapter-segment-btn')[2]!.trigger('click')
    expect(wrapper.findAll('.chapter-jump-item').length).toBe(40)
    await wrapper.find('.chapter-jump-expand').trigger('click')
    expect(wrapper.findAll('.chapter-jump-item').length).toBe(100)

    // Empty query renders message outside listbox role
    const input = wrapper.find('.chapter-jump-input')
    await input.setValue('不存在的章节XYZ')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(wrapper.find('.chapter-jump-empty').text()).toContain('未找到匹配章节')

    // Valid search & item click emits change
    await input.setValue('205')
    await wrapper.find('.chapter-jump-item').trigger('click')
    expect(wrapper.emitted('change')?.[0]).toEqual(['chap_205'])

    wrapper.unmount()
  })

  it('preserves duplicate chapter ordinals and non-1-based edge labels', async () => {
    const chapters: Chapter[] = Array.from({ length: 60 }, (_, i) => ({
      id: `chap_${i}`,
      index: i === 58 ? 5 : i,
      title: `话 ${i}`,
      start: i * 10 + 1,
      page_count: 10,
      cover_path: `/cover_${i}.webp`,
    }))

    const wrapper = mount(ChapterSwitcher, {
      props: {
        chapters,
        activeId: 'chap_30',
      },
      attachTo: document.body,
    })

    const leftEdgeBtn = wrapper.find('button.chapter-edge-jump--start')
    expect(leftEdgeBtn.find('.chapter-edge-range').text()).toBe('0–13')

    await wrapper.find('.chapter-jump-trigger').trigger('click')
    await nextTick()
    await wrapper.find('.chapter-jump-input').setValue('5')

    const exactMatches = wrapper
      .findAll('.chapter-jump-item')
      .filter((item) => item.find('.chapter-jump-idx').text() === '5')
    expect(exactMatches.length).toBe(2)

    wrapper.unmount()
  })

  it('falls back to sentinel IntersectionObserver when scroll-timeline is unsupported', async () => {
    const hadCSS = 'CSS' in globalThis
    const originalCSS = globalThis.CSS
    const originalIO = globalThis.IntersectionObserver

    let capturedCallback: IntersectionObserverCallback | null = null
    const observedTargets: Element[] = []
    const disconnectSpy = vi.fn<() => void>()

    globalThis.CSS = {
      ...globalThis.CSS,
      supports: () => false,
    } as typeof CSS

    globalThis.IntersectionObserver = class MockIO {
      constructor(cb: IntersectionObserverCallback) {
        capturedCallback = cb
      }
      observe(target: Element) {
        observedTargets.push(target)
      }
      disconnect() {
        disconnectSpy()
      }
      unobserve() {}
      takeRecords() {
        return []
      }
      readonly root = null
      readonly rootMargin = ''
      readonly thresholds = [0]
    } as unknown as typeof IntersectionObserver

    try {
      const wrapper = mount(ChapterSwitcher, {
        props: {
          chapters: makeChapters(5),
          activeId: 'chap_3',
        },
        attachTo: document.body,
      })

      await nextTick()
      expect(observedTargets.length).toBe(2)
      expect(capturedCallback).toBeTruthy()

      const startSentinel = wrapper.find('.scroll-sentinel--start').element
      const endSentinel = wrapper.find('.scroll-sentinel--end').element

      capturedCallback!(
        [
          { target: startSentinel, isIntersecting: false } as IntersectionObserverEntry,
          { target: endSentinel, isIntersecting: true } as IntersectionObserverEntry,
        ],
        {} as IntersectionObserver,
      )

      const container = wrapper.find('.chapter-switcher').element as HTMLElement
      expect(container.dataset.scrollLeft).toBe('true')
      expect(container.dataset.scrollRight).toBe('false')

      wrapper.unmount()
      expect(disconnectSpy).toHaveBeenCalled()
    } finally {
      if (hadCSS) {
        globalThis.CSS = originalCSS
      } else {
        delete (globalThis as Partial<typeof globalThis>).CSS
      }
      globalThis.IntersectionObserver = originalIO
    }
  })
})

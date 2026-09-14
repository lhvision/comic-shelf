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
})

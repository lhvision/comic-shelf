import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import BackToTop from '@/components/BackToTop.vue'

const scrollY = ref(0)

vi.mock('@vueuse/core', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    useWindowScroll: () => ({
      x: ref(0),
      y: scrollY,
    }),
  }
})

describe('BackToTop', () => {
  beforeEach(() => {
    scrollY.value = 0
    vi.restoreAllMocks()
  })

  it('remains hidden when scroll distance is below threshold', () => {
    scrollY.value = 200
    const wrapper = mount(BackToTop)

    expect(wrapper.find('.back-to-top').exists()).toBe(false)
  })

  it('becomes visible when scroll distance exceeds default threshold (400px)', () => {
    scrollY.value = 450
    const wrapper = mount(BackToTop)

    expect(wrapper.find('.back-to-top').exists()).toBe(true)
    const btn = wrapper.find('.back-to-top-btn')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('aria-label')).toBe('回到顶部')
  })

  it('respects custom threshold prop', () => {
    scrollY.value = 250
    const wrapper = mount(BackToTop, {
      props: { threshold: 200 },
    })

    expect(wrapper.find('.back-to-top').exists()).toBe(true)
  })

  it('calls window.scrollTo with top 0 and smooth behavior on click by default', async () => {
    scrollY.value = 500
    const scrollToMock = vi.fn<(options?: ScrollToOptions) => void>()
    window.scrollTo = scrollToMock

    const wrapper = mount(BackToTop)
    const btn = wrapper.find('.back-to-top-btn')
    await btn.trigger('click')

    expect(scrollToMock).toHaveBeenCalledWith({
      top: 0,
      behavior: 'smooth',
    })
  })

  it('respects prefers-reduced-motion by using behavior auto', async () => {
    scrollY.value = 500
    const scrollToMock = vi.fn<(options?: ScrollToOptions) => void>()
    window.scrollTo = scrollToMock

    window.matchMedia = vi
      .fn<(query: string) => MediaQueryList>()
      .mockImplementation((query: string) => ({
        matches: query.includes('prefers-reduced-motion: reduce'),
        media: query,
        onchange: null,
        addListener: vi.fn<() => void>(),
        removeListener: vi.fn<() => void>(),
        addEventListener: vi.fn<() => void>(),
        removeEventListener: vi.fn<() => void>(),
        dispatchEvent: vi.fn<() => boolean>().mockReturnValue(true),
      }))

    const wrapper = mount(BackToTop)
    const btn = wrapper.find('.back-to-top-btn')
    await btn.trigger('click')

    expect(scrollToMock).toHaveBeenCalledWith({
      top: 0,
      behavior: 'auto',
    })
  })

  it('safely focuses main element on click to prevent focus loss', async () => {
    scrollY.value = 500
    window.scrollTo = vi.fn<() => void>()
    const mainEl = document.createElement('main')
    mainEl.className = 'app-main'
    document.body.appendChild(mainEl)

    const wrapper = mount(BackToTop, {
      attachTo: document.body,
    })
    try {
      const btn = wrapper.find('.back-to-top-btn')
      await btn.trigger('click')

      expect(document.activeElement).toBe(mainEl)
      expect(mainEl.getAttribute('tabindex')).toBe('-1')
    } finally {
      document.body.removeChild(mainEl)
      wrapper.unmount()
    }
  })
})

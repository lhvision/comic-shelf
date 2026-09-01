import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useIdlePrefetch } from '@/composables/useIdlePrefetch'

describe('useIdlePrefetch', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('schedules prefetching via requestIdleCallback when supported', async () => {
    const loader = vi.fn<() => Promise<Record<string, unknown>>>().mockResolvedValue({})
    const requestIdleCallbackMock = vi.fn<
      (callback: IdleRequestCallback, options?: IdleRequestOptions) => number
    >((cb: IdleRequestCallback) => {
      // simulate asynchronous execution
      setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 10)
      return 123
    })
    const cancelIdleCallbackMock = vi.fn<(handle: number) => void>()

    vi.stubGlobal('requestIdleCallback', requestIdleCallbackMock)
    vi.stubGlobal('cancelIdleCallback', cancelIdleCallbackMock)

    const TestComponent = defineComponent({
      setup() {
        useIdlePrefetch(loader, { timeout: 4000 })
        return () => h('div')
      },
    })

    const wrapper = mount(TestComponent)
    expect(requestIdleCallbackMock).toHaveBeenCalledWith(expect.any(Function), { timeout: 4000 })

    vi.advanceTimersByTime(20)
    expect(loader).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('falls back to setTimeout when requestIdleCallback is unavailable', async () => {
    const loader = vi.fn<() => Promise<Record<string, unknown>>>().mockResolvedValue({})

    // Delete requestIdleCallback if present
    const original = window.requestIdleCallback
    // @ts-expect-error delete for testing fallback
    delete window.requestIdleCallback

    const TestComponent = defineComponent({
      setup() {
        useIdlePrefetch(loader, { fallbackDelay: 1500 })
        return () => h('div')
      },
    })

    const wrapper = mount(TestComponent)

    expect(loader).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1499)
    expect(loader).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(loader).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    if (original) {
      window.requestIdleCallback = original
    }
  })

  it('cancels scheduled prefetch when unmounted before trigger', () => {
    const loader = vi.fn<() => Promise<Record<string, unknown>>>().mockResolvedValue({})
    const cancelIdleCallbackMock = vi.fn<(handle: number) => void>()
    const requestIdleCallbackMock = vi.fn<
      (callback: IdleRequestCallback, options?: IdleRequestOptions) => number
    >(() => 999)

    vi.stubGlobal('requestIdleCallback', requestIdleCallbackMock)
    vi.stubGlobal('cancelIdleCallback', cancelIdleCallbackMock)

    const TestComponent = defineComponent({
      setup() {
        useIdlePrefetch(loader)
        return () => h('div')
      },
    })

    const wrapper = mount(TestComponent)
    wrapper.unmount()

    expect(cancelIdleCallbackMock).toHaveBeenCalledWith(999)
  })
})

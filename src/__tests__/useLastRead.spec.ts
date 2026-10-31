import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { effectScope, nextTick, ref } from 'vue'
import { useLastRead } from '@/composables/useLastRead'
import { api } from '@/api/client'

describe('useLastRead LWW synchronization', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('adopts server progress when server record is newer than local timestamp', async () => {
    vi.spyOn(api, 'getReadingProgress').mockResolvedValue({
      ok: true,
      last_page: 25,
      total_pages: 50,
      updated_at: 2000,
    })

    const source = ref('jm')
    const sourceId = ref('123')

    const scope = effectScope()
    let lastReadRef: { value: number } | undefined
    scope.run(() => {
      lastReadRef = useLastRead(source, sourceId)
    })

    await nextTick()
    await nextTick()

    expect(lastReadRef?.value).toBe(25)
    scope.stop()
  })

  it('preserves local progress when reader intentionally rewinds and local timestamp is newer', async () => {
    vi.useFakeTimers()
    const saveSpy = vi.spyOn(api, 'saveReadingProgress').mockResolvedValue({
      ok: true,
      last_page: 1,
      total_pages: 50,
      updated_at: 3000,
    })

    // Local already has page 1 recorded with timestamp 3000
    const source = ref('jm')
    const sourceId = ref('456')
    localStorage.setItem('comic-shelf:last-read:default:jm/456', '1')
    localStorage.setItem('comic-shelf:last-read:default:jm/456:ts', '3000')

    // Server returns older record (page 40, updated at 1000)
    vi.spyOn(api, 'getReadingProgress').mockResolvedValue({
      ok: true,
      last_page: 40,
      total_pages: 50,
      updated_at: 1000,
    })

    const scope = effectScope()
    let lastReadRef: { value: number } | undefined
    scope.run(() => {
      lastReadRef = useLastRead(source, sourceId)
    })

    await nextTick()
    await nextTick()

    // Local progress 1 MUST NOT be overwritten by server 40!
    expect(lastReadRef?.value).toBe(1)

    // Advance debounce timer (800ms)
    vi.advanceTimersByTime(800)
    expect(saveSpy).toHaveBeenCalledWith('jm', '456', 1)

    scope.stop()
    vi.useRealTimers()
  })

  it('flushes pending progress on window pagehide and scope disposal', async () => {
    const saveSpy = vi.spyOn(api, 'saveReadingProgress').mockResolvedValue({
      ok: true,
      last_page: 15,
      total_pages: 50,
      updated_at: 4000,
    })
    vi.spyOn(api, 'getReadingProgress').mockResolvedValue({
      ok: true,
      last_page: 0,
      total_pages: 50,
      updated_at: 0,
    })

    const source = ref('jm')
    const sourceId = ref('789')

    const scope = effectScope()
    let lastReadRef: { value: number } | undefined
    scope.run(() => {
      lastReadRef = useLastRead(source, sourceId)
    })

    await nextTick()
    // Turn page to 15
    if (lastReadRef) {
      lastReadRef.value = 15
    }
    // Allow watch(storage) to fire and queue reportProgress
    await nextTick()

    // Simulate pagehide before debounce 800ms expires
    window.dispatchEvent(new Event('pagehide'))

    expect(saveSpy).toHaveBeenCalledWith('jm', '789', 15)

    scope.stop()
  })
})

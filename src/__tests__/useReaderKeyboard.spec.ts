import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { ref, computed } from 'vue'
import { useReaderKeyboard } from '@/composables/useReaderKeyboard'
import type { ReaderSettings } from '@/composables/useReaderSettings'

describe('useReaderKeyboard - Cascading Escape & Filmstrip Toggle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })
  const defaultSettings: ReaderSettings = {
    mode: 'horizontal',
    direction: 'ltr',
    pagesPerView: 1,
    fit: 'width',
    autoTurn: false,
    autoTurnInterval: 5,
    seamless: false,
  }

  function setupKeyboard(overrides: Partial<Parameters<typeof useReaderKeyboard>[0]> = {}) {
    const settingsOpen = ref(false)
    const filmstripOpen = ref(false)
    const total = computed(() => 10)
    const goToPage = vi.fn<(page: number) => void>()
    const prevGroup = vi.fn<() => void>()
    const nextGroup = vi.fn<() => void>()
    const goNextChapter = vi.fn<() => void>()
    const goPrevChapter = vi.fn<() => void>()
    const backToDetail = vi.fn<() => void>()
    const toggleFilmstrip = vi.fn<() => void>(() => {
      filmstripOpen.value = !filmstripOpen.value
    })
    const onUserInteract = vi.fn<() => void>()

    const result = useReaderKeyboard({
      settingsOpen,
      filmstripOpen,
      toggleFilmstrip,
      settings: defaultSettings,
      total,
      goToPage,
      prevGroup,
      nextGroup,
      goNextChapter,
      goPrevChapter,
      backToDetail,
      onUserInteract,
      ...overrides,
    })

    return {
      settingsOpen,
      filmstripOpen,
      toggleFilmstrip,
      backToDetail,
      onUserInteract,
      ...result,
    }
  }

  it('cascades Escape key: closes settingsOpen first', () => {
    const state = setupKeyboard()
    state.settingsOpen.value = true
    state.filmstripOpen.value = true

    const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
    state.onKeydown(event)

    expect(state.settingsOpen.value).toBe(false)
    expect(state.filmstripOpen.value).toBe(true)
    expect(state.backToDetail).not.toHaveBeenCalled()
  })

  it('cascades Escape key: closes filmstripOpen second', () => {
    const state = setupKeyboard()
    state.settingsOpen.value = false
    state.filmstripOpen.value = true

    const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
    state.onKeydown(event)

    expect(state.filmstripOpen.value).toBe(false)
    expect(state.backToDetail).not.toHaveBeenCalled()
  })

  it('cascades Escape key: exits to detail only when no popovers are open', () => {
    const state = setupKeyboard()
    state.settingsOpen.value = false
    state.filmstripOpen.value = false

    const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
    state.onKeydown(event)

    expect(state.backToDetail).toHaveBeenCalled()
  })

  it('toggles filmstrip with "t" or "s" key', () => {
    const state = setupKeyboard()

    state.onKeydown(new KeyboardEvent('keydown', { key: 't' }))
    expect(state.toggleFilmstrip).toHaveBeenCalledTimes(1)
    expect(state.filmstripOpen.value).toBe(true)

    state.onKeydown(new KeyboardEvent('keydown', { key: 's' }))
    expect(state.toggleFilmstrip).toHaveBeenCalledTimes(2)
    expect(state.filmstripOpen.value).toBe(false)
  })

  it('handles repeating ArrowRight: uses "auto" behavior, throttles repeats, and fires onKeyRelease on keyup', async () => {
    const nextGroup = vi.fn<(behavior?: ScrollBehavior) => void>()
    const onKeyRelease = vi.fn<() => void>()
    const state = setupKeyboard({ nextGroup, onKeyRelease })

    // 1. First non-repeating keydown triggers with 'smooth' behavior
    const firstEvent = new KeyboardEvent('keydown', { key: 'ArrowRight', repeat: false })
    state.onKeydown(firstEvent)
    expect(nextGroup).toHaveBeenCalledWith('smooth')
    expect(nextGroup).toHaveBeenCalledTimes(1)

    // 2. High-frequency repeating keydown immediately after (< 110ms) is throttled
    const fastRepeatEvent = new KeyboardEvent('keydown', { key: 'ArrowRight', repeat: true })
    state.onKeydown(fastRepeatEvent)
    expect(nextGroup).toHaveBeenCalledTimes(1)

    // 3. Repeating keydown after 120ms passes 'auto' behavior
    vi.advanceTimersByTime(120)
    state.onKeydown(fastRepeatEvent)
    expect(nextGroup).toHaveBeenCalledTimes(2)
    expect(nextGroup).toHaveBeenLastCalledWith('auto')

    // 4. Releasing the key triggers onKeyRelease
    state.onKeyup(new KeyboardEvent('keyup', { key: 'ArrowRight' }))
    expect(onKeyRelease).toHaveBeenCalledTimes(1)
  })

  it('ignores keydown when modifier keys (ctrlKey, metaKey, altKey) are pressed to avoid hijacking browser shortcuts', () => {
    const nextGroup = vi.fn<() => void>()
    const goNextChapter = vi.fn<() => void>()
    const state = setupKeyboard({ nextGroup, goNextChapter })

    // Ctrl+S / Cmd+S should NOT toggle filmstrip
    state.onKeydown(new KeyboardEvent('keydown', { key: 's', ctrlKey: true }))
    state.onKeydown(new KeyboardEvent('keydown', { key: 's', metaKey: true }))
    // Ctrl+T should NOT toggle filmstrip
    state.onKeydown(new KeyboardEvent('keydown', { key: 't', ctrlKey: true }))
    expect(state.toggleFilmstrip).not.toHaveBeenCalled()

    // Ctrl+Right should NOT advance
    state.onKeydown(new KeyboardEvent('keydown', { key: 'ArrowRight', ctrlKey: true }))
    expect(nextGroup).not.toHaveBeenCalled()

    // Alt+N should NOT jump chapter
    state.onKeydown(new KeyboardEvent('keydown', { key: 'n', altKey: true }))
    expect(goNextChapter).not.toHaveBeenCalled()
  })
})

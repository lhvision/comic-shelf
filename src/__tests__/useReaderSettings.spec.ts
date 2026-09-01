import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { useReaderSettings, DEFAULT_SETTINGS, SETTINGS_KEY } from '@/composables/useReaderSettings'

describe('useReaderSettings composable', () => {
  beforeEach(() => {
    localStorage.removeItem(SETTINGS_KEY)
  })

  it('initializes with default settings', () => {
    const { settings, reset } = useReaderSettings()
    reset()
    expect(settings.mode).toBe(DEFAULT_SETTINGS.mode)
    expect(settings.fit).toBe(DEFAULT_SETTINGS.fit)
    expect(settings.pagesPerView).toBe(DEFAULT_SETTINGS.pagesPerView)
    expect(settings.direction).toBe(DEFAULT_SETTINGS.direction)
    expect(settings.autoTurn).toBe(DEFAULT_SETTINGS.autoTurn)
    expect(settings.autoTurnInterval).toBe(DEFAULT_SETTINGS.autoTurnInterval)
  })

  it('correctly persists and allows fit width and height', () => {
    const { settings } = useReaderSettings()

    settings.fit = 'width'
    expect(settings.fit).toBe('width')

    settings.fit = 'height'
    expect(settings.fit).toBe('height')
  })

  it('correctly updates mode and direction', () => {
    const { settings } = useReaderSettings()

    settings.mode = 'horizontal'
    expect(settings.mode).toBe('horizontal')

    settings.direction = 'rtl'
    expect(settings.direction).toBe('rtl')

    settings.mode = 'vertical-paged'
    expect(settings.mode).toBe('vertical-paged')
  })

  it('resets settings to default values', () => {
    const { settings, reset } = useReaderSettings()

    settings.fit = 'width'
    settings.mode = 'horizontal'
    settings.direction = 'rtl'
    settings.autoTurn = true
    settings.autoTurnInterval = 25

    reset()

    expect(settings.mode).toBe(DEFAULT_SETTINGS.mode)
    expect(settings.fit).toBe(DEFAULT_SETTINGS.fit)
    expect(settings.direction).toBe(DEFAULT_SETTINGS.direction)
    expect(settings.autoTurn).toBe(DEFAULT_SETTINGS.autoTurn)
    expect(settings.autoTurnInterval).toBe(DEFAULT_SETTINGS.autoTurnInterval)
  })
})

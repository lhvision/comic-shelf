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
    expect(settings.seamless).toBe(DEFAULT_SETTINGS.seamless)
  })

  it('enforces single page and fit width constraints when seamless strip mode is enabled', async () => {
    const { settings, reset } = useReaderSettings()
    reset()
    settings.mode = 'vertical-continuous'
    settings.pagesPerView = 2
    settings.fit = 'height'

    settings.seamless = true
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(settings.seamless).toBe(true)
    expect(settings.pagesPerView).toBe(1)
    expect(settings.fit).toBe('width')
  })

  it('applies per-comic preferences and auto-detects strip manga tags', async () => {
    const { settings, reset, applyComicPreferences, clearActiveComic } = useReaderSettings()
    reset()

    // 普通日漫：无条漫标签，遵循全局默认 seamless = false
    applyComicPreferences('jm', '10001', ['同人志', '全彩'])
    expect(settings.seamless).toBe(false)
    clearActiveComic()

    // 韩漫/条漫：命中条漫标签，自动赋初值 seamless = true
    applyComicPreferences('jm', '518074', ['韩漫', '条漫', '全彩'])
    expect(settings.seamless).toBe(true)
    expect(settings.fit).toBe('width')

    // 用户在条漫中主动修改设置后会持久化覆盖
    settings.fit = 'height' // 尝试修改，由于 seamless 存在仍会被约束回 width
    expect(settings.fit).toBe('width')
    clearActiveComic()

    // 重新打开该条漫时能够读取记忆的单本偏好
    applyComicPreferences('jm', '518074', [])
    expect(settings.seamless).toBe(true)
    clearActiveComic()
  })
})

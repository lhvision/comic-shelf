import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { nextTick } from 'vue'
import {
  useReaderSettings,
  DEFAULT_SETTINGS,
  SETTINGS_KEY,
  OVERRIDES_KEY,
  MAX_OVERRIDES,
  clampSettings,
} from '@/composables/useReaderSettings'

describe('useReaderSettings composable', () => {
  beforeEach(() => {
    localStorage.removeItem(SETTINGS_KEY)
    localStorage.removeItem(OVERRIDES_KEY)
    const { clearActiveComic, reset } = useReaderSettings()
    clearActiveComic()
    reset()
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
    await nextTick()

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

    // 严密回归：退出条漫后再打开普通日漫，绝不应受到条漫 seamless=true 污染
    applyComicPreferences('jm', '10002', ['同人志'])
    expect(settings.seamless).toBe(false)
    expect(settings.fit).toBe(DEFAULT_SETTINGS.fit)
    expect(settings.pagesPerView).toBe(DEFAULT_SETTINGS.pagesPerView)
    clearActiveComic()
  })

  it('strictly isolates custom overrides between different comics', () => {
    const { settings, reset, applyComicPreferences, clearActiveComic } = useReaderSettings()
    reset()

    // 全局默认基线
    expect(settings.direction).toBe('ltr')

    // 漫画 A 设置为从右向左（日漫）
    applyComicPreferences('jm', 'comicA', [])
    settings.direction = 'rtl'
    expect(settings.direction).toBe('rtl')
    clearActiveComic()

    // 退出后回到全局基线
    expect(settings.direction).toBe('ltr')

    // 漫画 B 没有自定义过，保持全局基线 ltr
    applyComicPreferences('jm', 'comicB', [])
    expect(settings.direction).toBe('ltr')
    clearActiveComic()

    // 重新进入漫画 A，记忆其独立的 rtl
    applyComicPreferences('jm', 'comicA', [])
    expect(settings.direction).toBe('rtl')
    clearActiveComic()
  })

  it('resets only current comic overrides without clearing global settings', () => {
    const { settings, reset, applyComicPreferences, clearActiveComic } = useReaderSettings()
    reset()

    // 设置全局偏好为 autoTurn = true
    settings.autoTurn = true

    // 进入漫画 A 并设置其专属 direction
    applyComicPreferences('jm', 'comicA', [])
    settings.direction = 'rtl'
    expect(settings.direction).toBe('rtl')

    // 在漫画内点击重置，仅清除漫画 A 的专属偏好
    reset()
    expect(settings.direction).toBe('ltr')
    // 全局 autoTurn 设置得以保留
    expect(settings.autoTurn).toBe(true)
    clearActiveComic()

    // 全局依然保留 autoTurn = true
    expect(settings.autoTurn).toBe(true)
  })

  it('enforces MAX_OVERRIDES capacity capping and evicts oldest entries', () => {
    const { applyComicPreferences, clearActiveComic } = useReaderSettings()

    // 连续写入超过 MAX_OVERRIDES 本漫画偏好
    for (let i = 0; i < MAX_OVERRIDES + 10; i++) {
      applyComicPreferences('jm', `comic_${i}`, ['条漫'])
      clearActiveComic()
    }

    const storedOverrides = JSON.parse(localStorage.getItem(OVERRIDES_KEY) || '{}')
    const keys = Object.keys(storedOverrides)
    expect(keys.length).toBeLessThanOrEqual(MAX_OVERRIDES)
    // 最早的 key 应当已被驱逐
    expect(storedOverrides['jm:comic_0']).toBeUndefined()
    // 最新的 key 应当存在
    expect(storedOverrides[`jm:comic_${MAX_OVERRIDES + 9}`]).toBeDefined()
  })

  it('sanitizes and clamps dirty or corrupted settings against schema invariants', () => {
    // 模拟从外部注入或早期受损的异常脏数据
    const malformed = {
      mode: 'unsupported_mode' as unknown as 'vertical-continuous',
      pagesPerView: 999 as unknown as 1,
      fit: 'malformed_fit' as unknown as 'width',
      autoTurnInterval: -50,
      seamless: true,
    }

    const sanitized = clampSettings(malformed, false)

    // 非法模式回退到默认
    expect(sanitized.mode).toBe(DEFAULT_SETTINGS.mode)
    // seamless 强制锁定 fit='width', ppv=1
    expect(sanitized.fit).toBe('width')
    expect(sanitized.pagesPerView).toBe(1)
    // 异常翻页间隔自动收敛到默认值
    expect(sanitized.autoTurnInterval).toBe(DEFAULT_SETTINGS.autoTurnInterval)

    // 在窄屏视口下，即使传入 4 连页也会被收敛为 1 页
    const clampedNarrow = clampSettings({ pagesPerView: 4 }, false)
    expect(clampedNarrow.pagesPerView).toBe(1)

    // 在宽屏视口下，4 连页允许保留
    const clampedWide = clampSettings({ pagesPerView: 4 }, true)
    expect(clampedWide.pagesPerView).toBe(4)
  })

  it('supports dual scope: editing globalSettings updates global baseline and live-syncs to inheriting comics', async () => {
    const {
      settings,
      globalSettings,
      hasActiveOverride,
      isInheritingGlobal,
      applyComicPreferences,
      clearActiveComic,
    } = useReaderSettings()

    // 进入一本普通漫画，处于完全继承全局状态
    applyComicPreferences('jm', 'comic_inherit', ['同人'])
    expect(hasActiveOverride.value).toBe(false)
    expect(isInheritingGlobal.value).toBe(true)
    expect(settings.fit).toBe('height')

    // 修改全局基准为 fit='width'
    globalSettings.fit = 'width'
    await nextTick()

    // 继承态漫画视口必须实时同步
    expect(settings.fit).toBe('width')

    // 退出当前漫画，打开一本全新漫画，也必须继承最新的全局基线
    clearActiveComic()
    applyComicPreferences('jm', 'comic_new', [])
    expect(settings.fit).toBe('width')
  })

  it('supports reverting per-comic overrides to follow global baseline', async () => {
    const {
      settings,
      globalSettings,
      hasActiveOverride,
      isInheritingGlobal,
      applyComicPreferences,
      revertToGlobal,
      clearActiveComic,
    } = useReaderSettings()

    // 确保全局基线为 fit='height'
    globalSettings.fit = 'height'

    // 进入漫画并设置独立覆盖为 fit='width'
    applyComicPreferences('jm', 'comic_custom', [])
    settings.fit = 'width'
    await nextTick()

    expect(hasActiveOverride.value).toBe(true)
    expect(isInheritingGlobal.value).toBe(false)
    expect(settings.fit).toBe('width')
    expect(globalSettings.fit).toBe('height') // 全局不被污染

    // 恢复跟随全局
    revertToGlobal()
    await nextTick()

    expect(hasActiveOverride.value).toBe(false)
    expect(isInheritingGlobal.value).toBe(true)
    expect(settings.fit).toBe('height')

    clearActiveComic()
  })

  it('correctly persists autoTurn and autoTurnInterval in per-comic overrides', async () => {
    const {
      settings,
      globalSettings,
      hasActiveOverride,
      applyComicPreferences,
      revertToGlobal,
      clearActiveComic,
    } = useReaderSettings()

    // 全局基线 autoTurnInterval 为默认值 10，autoTurn 为 false
    expect(globalSettings.autoTurnInterval).toBe(10)
    expect(globalSettings.autoTurn).toBe(false)

    // 进入漫画并在单本偏好中修改自动翻页与秒数
    applyComicPreferences('jm', 'comic_turn_test', [])
    settings.autoTurn = true
    settings.autoTurnInterval = 25
    await nextTick()

    expect(hasActiveOverride.value).toBe(true)
    expect(settings.autoTurn).toBe(true)
    expect(settings.autoTurnInterval).toBe(25)
    expect(globalSettings.autoTurn).toBe(false) // 全局未被污染
    expect(globalSettings.autoTurnInterval).toBe(10)

    // 退出后重新打开该漫画，专属偏好必须正确复原
    clearActiveComic()
    applyComicPreferences('jm', 'comic_turn_test', [])
    expect(hasActiveOverride.value).toBe(true)
    expect(settings.autoTurn).toBe(true)
    expect(settings.autoTurnInterval).toBe(25)

    // 恢复跟随全局后，退回全局基线
    revertToGlobal()
    await nextTick()
    expect(settings.autoTurn).toBe(false)
    expect(settings.autoTurnInterval).toBe(10)

    clearActiveComic()
  })
})

import { computed, reactive, ref, watch } from 'vue'
import { createGlobalState, useLocalStorage, useMediaQuery } from '@vueuse/core'

/**
 * 阅读器设置 —— 单一事实来源（single source of truth）。
 *
 * 这套设置被 ReaderView 与 ReaderSettingsPanel 共享，且跨路由重挂载后需要保留，
 * 因此用 `createGlobalState` 提升为模块级单例，再用 `useLocalStorage` 持久化到
 * `comic-shelf:reader-settings:v1`（保持旧 key，兼容已存用户的设置）。
 *
 * 为什么是 createGlobalState 而不是 Pinia：
 * - 设置是"一个对象、多处读、一处改"，没有跨页的复杂派生逻辑；
 * - 用 VueUse 的 storage 组合式函数即可覆盖持久化，不必再引入 store 层。
 */

export type ReaderMode = 'vertical-continuous' | 'vertical-paged' | 'horizontal'
export type FitMode = 'width' | 'height'
export type SpreadDirection = 'ltr' | 'rtl'
export type AutoTurnInterval = number

export interface ReaderSettings {
  mode: ReaderMode
  fit: FitMode
  pagesPerView: 1 | 2 | 4
  direction: SpreadDirection
  autoTurn: boolean
  autoTurnInterval: AutoTurnInterval
  seamless: boolean
}

/** 兼容旧版本设置用的 localStorage key，禁止随意改名 */
export const SETTINGS_KEY = 'comic-shelf:reader-settings:v1'
/** 作品级独立阅读偏好持久化 key */
export const OVERRIDES_KEY = 'comic-shelf:reader-overrides:v1'
/** 历史受污设备全局基线自愈标记 key */
export const HEALED_KEY = 'comic-shelf:baseline-healed:v1'
/** 单本作品偏好最大持久化缓存条目（防止 localStorage 无界膨胀） */
export const MAX_OVERRIDES = 100
export const AUTO_TURN_INTERVALS = [5, 10, 15, 30] as const
export const DEFAULT_SETTINGS: Readonly<ReaderSettings> = {
  mode: 'vertical-continuous',
  fit: 'height',
  pagesPerView: 1,
  direction: 'ltr',
  autoTurn: false,
  autoTurnInterval: 10,
  seamless: false,
}

/** 桌面端判定断点：>680px 才允许 4 连页 */
export const WIDE_VIEWPORT_QUERY = '(min-width: 681px)'

/** 设置面板的静态选项（不依赖视口宽度，可放模块级） */
export const MODE_OPTIONS: Array<{ value: ReaderMode; label: string; hint: string }> = [
  { value: 'vertical-continuous', label: '竖向连续', hint: '无吸附，自由滚到底' },
  { value: 'vertical-paged', label: '竖向翻页', hint: '一次一屏，整页可见' },
  { value: 'horizontal', label: '横向翻页', hint: '左右滑动切页' },
]

export const FIT_OPTIONS: Array<{ value: FitMode; label: string }> = [
  { value: 'width', label: '适应宽度' },
  { value: 'height', label: '适应高度' },
]

export const AUTO_TURN_OPTIONS: Array<{ value: number; label: string }> = AUTO_TURN_INTERVALS.map(
  (seconds) => ({ value: seconds, label: `${seconds} 秒` }),
)

/**
 * 归一化设置值：只信任合法枚举，非法/缺失取值回落默认。
 * 空值兼容：旧版本存储里可能没有某些字段（如 autoTurn / autoTurnInterval）。
 */
export function clampSettings(
  value: Partial<ReaderSettings>,
  wideViewport: boolean,
): ReaderSettings {
  const rawInterval = value.autoTurnInterval
  const autoTurnInterval =
    typeof rawInterval === 'number' &&
    Number.isFinite(rawInterval) &&
    rawInterval >= 1 &&
    rawInterval <= 300
      ? Math.round(rawInterval)
      : DEFAULT_SETTINGS.autoTurnInterval

  const finalMode =
    value.mode === 'vertical-continuous' ||
    value.mode === 'vertical-paged' ||
    value.mode === 'horizontal'
      ? value.mode
      : DEFAULT_SETTINGS.mode

  const isSeamless = value.seamless === true
  const isContinuousSeamless = finalMode === 'vertical-continuous' && isSeamless

  const pagesPerView = value.pagesPerView
  const allowedPages = wideViewport ? ([1, 2, 4] as const) : ([1, 2] as const)
  const normalizedPages: 1 | 2 | 4 =
    pagesPerView === 1 || pagesPerView === 2 || pagesPerView === 4
      ? allowedPages.some((entry) => entry === pagesPerView)
        ? pagesPerView
        : 1
      : DEFAULT_SETTINGS.pagesPerView

  const finalFit = isContinuousSeamless
    ? 'width'
    : value.fit === 'width' || value.fit === 'height'
      ? value.fit
      : DEFAULT_SETTINGS.fit

  const finalPages = isContinuousSeamless ? 1 : normalizedPages

  return {
    mode: finalMode,
    fit: finalFit,
    pagesPerView: finalPages,
    direction:
      value.direction === 'ltr' || value.direction === 'rtl'
        ? value.direction
        : DEFAULT_SETTINGS.direction,
    autoTurn: value.autoTurn === true,
    autoTurnInterval,
    seamless: isSeamless,
  }
}

/**
 * 全局单例的阅读器设置（双轨制架构：全局基线 + 单本覆盖）。任何组件调用返回同一个对象：
 * - settings：当前阅读器活跃生效的设置对象（直接供阅读器视口消费）
 * - globalSettings：全站通用基线设置对象（修改即时同步至新收录漫画及继承中的漫画）
 * - hasActiveOverride：当前作品是否已建立独立专属偏好
 * - isInheritingGlobal：当前作品是否处于完全继承全局默认基线状态
 * - activeComicIsStrip：当前作品是否命中条漫自适应无缝拼接
 * - revertToGlobal：清除当前作品独立偏好，恢复跟随全局基线
 * - resetGlobalBaseline：将全站通用基线重置为出厂初始值
 * - isWideViewport：响应式视口判断
 * - pagesPerViewOptions：随视口变化的可选页数（窄屏只有 1/2）
 * - reset：上下文敏感的恢复默认（作品有覆盖则恢复跟随，否则恢复基线）
 * - applyComicPreferences：根据漫画来源、ID 与标签应用单本偏好或自适应启用条漫无缝模式
 * - clearActiveComic：退出阅读时清理活跃漫画上下文
 */
export const useReaderSettings = createGlobalState(() => {
  // 直接以 v1 key 绑定本地存储；parse 失败时 useLocalStorage 会自动回落到 default
  const stored = useLocalStorage<Partial<ReaderSettings>>(
    SETTINGS_KEY,
    {},
    {
      flush: 'sync',
      listenToStorageChanges: false,
      onError: (e) => {
        console.error('USE_STORAGE_SETTINGS_ERROR:', e)
      },
    },
  )
  const overrides = useLocalStorage<Record<string, Partial<ReaderSettings>>>(
    OVERRIDES_KEY,
    {},
    {
      flush: 'sync',
      listenToStorageChanges: false,
      onError: (e) => {
        console.error('USE_STORAGE_OVERRIDES_ERROR:', e)
      },
    },
  )
  const healed = useLocalStorage<boolean>(HEALED_KEY, false)

  // 历史受污设备全局基线一次性静默自愈：若全局基线存有 fit='width' 且非条漫无缝，自动纠正回默认 height
  if (!healed.value) {
    if (stored.value.fit === 'width' && stored.value.seamless !== true) {
      stored.value = { ...stored.value, fit: 'height' }
    }
    healed.value = true
  }

  const activeComicKey = ref<string | null>(null)
  const isWideViewport = useMediaQuery(WIDE_VIEWPORT_QUERY)

  let isApplyingPreferences = false

  const globalSettings = reactive<ReaderSettings>(clampSettings(stored.value, isWideViewport.value))
  const settings = reactive<ReaderSettings>(clampSettings(stored.value, isWideViewport.value))

  const hasActiveOverride = computed(() =>
    Boolean(activeComicKey.value && overrides.value[activeComicKey.value]),
  )
  const isInheritingGlobal = computed(() =>
    Boolean(!activeComicKey.value || !overrides.value[activeComicKey.value]),
  )
  const activeComicIsStrip = computed(() =>
    Boolean(activeComicKey.value && overrides.value[activeComicKey.value]?.seamless === true),
  )

  // 视口收窄时把 4 连页强制收敛到 1 连页（窄屏默认单页阅读）
  watch(isWideViewport, (wide) => {
    if (!wide) {
      if (settings.pagesPerView === 4) settings.pagesPerView = 1
      if (globalSettings.pagesPerView === 4) globalSettings.pagesPerView = 1
    }
  })

  // 当处于竖向连续模式且开启无缝拼接时，强制锁定为单页且适应全宽（排版硬约束防撕裂）
  watch(
    () => [settings.mode, settings.seamless, settings.fit, settings.pagesPerView] as const,
    ([mode, seamless, fit, ppv]) => {
      if (mode === 'vertical-continuous' && seamless) {
        if (ppv !== 1) settings.pagesPerView = 1
        if (fit !== 'width') settings.fit = 'width'
      }
    },
    { immediate: true, flush: 'sync' },
  )

  watch(
    () =>
      [
        globalSettings.mode,
        globalSettings.seamless,
        globalSettings.fit,
        globalSettings.pagesPerView,
      ] as const,
    ([mode, seamless, fit, ppv]) => {
      if (mode === 'vertical-continuous' && seamless) {
        if (ppv !== 1) globalSettings.pagesPerView = 1
        if (fit !== 'width') globalSettings.fit = 'width'
      }
    },
    { immediate: true, flush: 'sync' },
  )

  /** 维护作品偏好的 FIFO / LRU 字典写入，防止 localStorage 无界膨胀 */
  function setOverride(key: string, patch: Partial<ReaderSettings>) {
    const current = { ...overrides.value }
    delete current[key]
    current[key] = { ...overrides.value[key], ...patch }
    const keys = Object.keys(current)
    if (keys.length > MAX_OVERRIDES) {
      for (let i = 0; i < keys.length - MAX_OVERRIDES; i++) {
        const evictKey = keys[i]
        if (evictKey) {
          delete current[evictKey]
        }
      }
    }
    overrides.value = current
  }

  // 全局基线写回：同步写入 stored.value；若当前作品处于继承全局状态，实时同步刷新视口 settings
  watch(
    globalSettings,
    (value) => {
      if (isApplyingPreferences) return
      stored.value = { ...DEFAULT_SETTINGS, ...value }
      if (isInheritingGlobal.value) {
        isApplyingPreferences = true
        Object.assign(settings, clampSettings(value, isWideViewport.value))
        isApplyingPreferences = false
      }
    },
    { deep: true, flush: 'sync' },
  )

  // 活跃设置写回：有活跃作品上下文时记入 overrides（即改即分离）；无作品时同步写回全局基线
  watch(
    settings,
    (value) => {
      if (isApplyingPreferences) return
      if (activeComicKey.value) {
        setOverride(activeComicKey.value, {
          mode: value.mode,
          fit: value.fit,
          pagesPerView: value.pagesPerView,
          direction: value.direction,
          seamless: value.seamless,
          autoTurn: value.autoTurn,
          autoTurnInterval: value.autoTurnInterval,
        })
      } else {
        stored.value = { ...DEFAULT_SETTINGS, ...value }
        isApplyingPreferences = true
        Object.assign(globalSettings, clampSettings(value, isWideViewport.value))
        isApplyingPreferences = false
      }
    },
    { deep: true, flush: 'sync' },
  )

  const pagesPerViewOptions = computed((): Array<1 | 2 | 4> =>
    isWideViewport.value ? [1, 2, 4] : [1, 2],
  )

  /**
   * 应用单本漫画阅读偏好（若首次打开且标签命中条漫/韩漫/Webtoon 特征，则智能默认启用无缝拼接）
   */
  function applyComicPreferences(source: string, sourceId: string, tags?: string[]) {
    if (!source || !sourceId) return
    const key = `${source}:${sourceId}`
    activeComicKey.value = key

    isApplyingPreferences = true
    const baseline = clampSettings(stored.value, isWideViewport.value)
    Object.assign(globalSettings, baseline)
    const custom = overrides.value[key]

    if (custom) {
      Object.assign(settings, clampSettings({ ...baseline, ...custom }, isWideViewport.value))
    } else {
      const isStrip =
        Array.isArray(tags) &&
        tags.some((tag) => typeof tag === 'string' && /条漫|條漫|韩漫|韓漫|webtoon/i.test(tag))
      if (isStrip) {
        Object.assign(
          settings,
          clampSettings({ ...baseline, seamless: true }, isWideViewport.value),
        )
        setOverride(key, { seamless: true })
      } else {
        Object.assign(settings, baseline)
      }
    }
    isApplyingPreferences = false
  }

  function clearActiveComic() {
    activeComicKey.value = null
    isApplyingPreferences = true
    const baseline = clampSettings(stored.value, isWideViewport.value)
    Object.assign(globalSettings, baseline)
    Object.assign(settings, baseline)
    isApplyingPreferences = false
  }

  /** 清除当前活跃漫画独立偏好，恢复跟随全局基线 */
  function revertToGlobal() {
    if (!activeComicKey.value) return
    isApplyingPreferences = true
    if (overrides.value[activeComicKey.value]) {
      const next = { ...overrides.value }
      delete next[activeComicKey.value]
      overrides.value = next
    }
    Object.assign(settings, clampSettings(globalSettings, isWideViewport.value))
    isApplyingPreferences = false
  }

  /** 将全站全局基线重置为出厂标准配置 */
  function resetGlobalBaseline() {
    isApplyingPreferences = true
    Object.assign(globalSettings, DEFAULT_SETTINGS)
    stored.value = { ...DEFAULT_SETTINGS }
    if (isInheritingGlobal.value) {
      Object.assign(settings, clampSettings(DEFAULT_SETTINGS, isWideViewport.value))
    }
    isApplyingPreferences = false
  }

  function reset() {
    if (activeComicKey.value && overrides.value[activeComicKey.value]) {
      revertToGlobal()
    } else {
      resetGlobalBaseline()
    }
  }

  return {
    settings,
    globalSettings,
    hasActiveOverride,
    isInheritingGlobal,
    activeComicIsStrip,
    revertToGlobal,
    resetGlobalBaseline,
    isWideViewport,
    pagesPerViewOptions,
    reset,
    applyComicPreferences,
    clearActiveComic,
  }
})

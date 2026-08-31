import { computed, reactive, watch } from 'vue'
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
}

/** 兼容旧版本设置用的 localStorage key，禁止随意改名 */
export const SETTINGS_KEY = 'comic-shelf:reader-settings:v1'
export const AUTO_TURN_INTERVALS = [5, 10, 15, 30] as const
export const DEFAULT_SETTINGS: Readonly<ReaderSettings> = {
  mode: 'vertical-continuous',
  fit: 'width',
  pagesPerView: 1,
  direction: 'ltr',
  autoTurn: false,
  autoTurnInterval: 10,
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
function clampSettings(value: Partial<ReaderSettings>, wideViewport: boolean): ReaderSettings {
  const pagesPerView = value.pagesPerView
  const allowedPages = wideViewport ? ([1, 2, 4] as const) : ([1, 2] as const)
  const normalizedPages: 1 | 2 | 4 =
    pagesPerView === 1 || pagesPerView === 2 || pagesPerView === 4
      ? allowedPages.some((entry) => entry === pagesPerView)
        ? pagesPerView
        : 2
      : DEFAULT_SETTINGS.pagesPerView
  const rawInterval = value.autoTurnInterval
  const autoTurnInterval =
    typeof rawInterval === 'number' &&
    Number.isFinite(rawInterval) &&
    rawInterval >= 1 &&
    rawInterval <= 300
      ? Math.round(rawInterval)
      : DEFAULT_SETTINGS.autoTurnInterval

  return {
    mode:
      value.mode === 'vertical-paged' || value.mode === 'horizontal'
        ? value.mode
        : DEFAULT_SETTINGS.mode,
    fit: value.fit === 'height' ? 'height' : DEFAULT_SETTINGS.fit,
    pagesPerView: normalizedPages,
    direction: value.direction === 'rtl' ? 'rtl' : DEFAULT_SETTINGS.direction,
    autoTurn: value.autoTurn === true,
    autoTurnInterval,
  }
}

/**
 * 全局单例的阅读器设置。任何组件调用返回同一个对象：
 * - settings：reactive 的设置对象（直接改、自动持久化）
 * - isWideViewport：响应式视口判断
 * - pagesPerViewOptions：随视口变化的可选页数（窄屏只有 1/2）
 * - reset：恢复默认
 */
export const useReaderSettings = createGlobalState(() => {
  // 直接以 v1 key 绑定本地存储；parse 失败时 useLocalStorage 会自动回落到 default
  const stored = useLocalStorage<Partial<ReaderSettings>>(SETTINGS_KEY, {})
  const isWideViewport = useMediaQuery(WIDE_VIEWPORT_QUERY)

  const settings = reactive<ReaderSettings>(clampSettings(stored.value, isWideViewport.value))

  // 视口收窄时把 4 连页强制收敛到 2 连页（横向翻页不允许窄屏 4 页）
  watch(isWideViewport, (wide) => {
    if (!wide && settings.pagesPerView === 4) settings.pagesPerView = 2
  })

  // 深度写回：任何子字段变化都同步到 localStorage（与 useStorage 的深 watch 行为一致）
  watch(
    settings,
    (value) => {
      stored.value = { ...DEFAULT_SETTINGS, ...value }
    },
    { deep: true },
  )

  const pagesPerViewOptions = computed((): Array<1 | 2 | 4> =>
    isWideViewport.value ? [1, 2, 4] : [1, 2],
  )

  function reset() {
    Object.assign(settings, DEFAULT_SETTINGS)
  }

  return { settings, isWideViewport, pagesPerViewOptions, reset }
})

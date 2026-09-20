/** 纸间类型守卫、浏览器环境探测与阅读状态判定。 */

export {
  isCompletedComic,
  isInProgressComic,
  isLocalComic,
  isPicacgComic,
  isJmComic,
} from '@/utils/libraryFilterCore'

/* ==========================================================================
   1. 基础类型守卫（Type Guards）
   ========================================================================== */

/**
 * 判定值是否为有效数值（排除 NaN）。
 */
export function isNumber(val: unknown): val is number {
  return typeof val === 'number' && !Number.isNaN(val)
}

/**
 * 判定值是否为有限数值（排除 NaN、±Infinity）。
 */
export function isFiniteNumber(val: unknown): val is number {
  return typeof val === 'number' && Number.isFinite(val)
}

/**
 * 判定值是否为字符串。
 */
export function isString(val: unknown): val is string {
  return typeof val === 'string'
}

/**
 * 判定值是否为数组。
 */
export function isArray<T = unknown>(val: unknown): val is T[] {
  return Array.isArray(val)
}

/* ==========================================================================
   2. 环境断言（Environment Predicates）
   ========================================================================== */

/**
 * 判定当前执行上下文是否具备完整浏览器 DOM 环境。
 */
export function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined'
}

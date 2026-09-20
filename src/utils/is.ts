/**
 * @file is.ts
 * @description 纸间全站类型守卫（Type Guards）、运行环境与领域状态断言工具集。
 *
 * 核心设计原则：
 * 1. 严格强类型收窄（TypeScript Type Narrowing）：
 *    所有判定函数均声明精准的 `val is T` 类型谓词，杜绝调用端出现二次非空断言与 `as` 强转；
 * 2. 单一真理源（Single Source of Truth）：
 *    收敛全站散落手写的 `typeof`、`Array.isArray` 以及漫画阅读/合集状态判断；
 * 3. 运行环境安全探测：
 *    支持 SSR/Node/Vitest 与浏览器无 DOM 环境下的安全执行。
 */

import {
  isCompletedComic,
  isInProgressComic,
  isUnreadComic,
  isMultiChapterComic,
  isLocalComic,
  isPicacgComic,
  isJmComic,
} from '@/utils/libraryFilterCore'

// 重导出领域状态断言
export {
  isCompletedComic,
  isInProgressComic,
  isUnreadComic,
  isMultiChapterComic,
  isLocalComic,
  isPicacgComic,
  isJmComic,
}

/* ==========================================================================
   1. 基础值与空值守卫（Value & Nil Guards）
   ========================================================================== */

/**
 * 判定值是否已定义且非 null/undefined。
 */
export function isDef<T>(val: T | null | undefined): val is T {
  return val !== null && val !== undefined
}

/**
 * 判定值是否为 null 或 undefined。
 */
export function isNil(val: unknown): val is null | undefined {
  return val === null || val === undefined
}

/* ==========================================================================
   2. 基础类型守卫（Type Guards）
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

/**
 * 判定值是否为普通对象（排除 null、Array、Date、RegExp、Set、Map 等复合实例）。
 */
export function isPlainObject(val: unknown): val is Record<string | number | symbol, unknown> {
  if (val === null || typeof val !== 'object') return false
  return Object.prototype.toString.call(val) === '[object Object]'
}

/**
 * 判定值是否为空（null, undefined, 空字符串, 空数组, 空 Set/Map 或无自身属性的普通对象）。
 */
export function isEmpty(val: unknown): boolean {
  if (val === null || val === undefined) return true
  if (typeof val === 'string') return val.trim().length === 0
  if (Array.isArray(val)) return val.length === 0
  if (val instanceof Set || val instanceof Map) return val.size === 0
  if (isPlainObject(val)) return Object.keys(val).length === 0
  return false
}

/* ==========================================================================
   5. 环境与网络断言（Environment & Network Predicates）
   ========================================================================== */

/**
 * 判定当前执行上下文是否具备完整浏览器 DOM 环境。
 */
export function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined'
}

/**
 * 判定当前宿主环境是否支持触控。
 */
export function isTouchDevice(): boolean {
  return (
    typeof window !== 'undefined' &&
    ('ontouchstart' in window || (typeof navigator !== 'undefined' && navigator.maxTouchPoints > 0))
  )
}

/**
 * 判定字符串是否为合法的 HTTP 或 HTTPS URL。
 */
export function isHttpUrl(url: string | null | undefined): boolean {
  if (!url || typeof url !== 'string') return false
  return /^https?:\/\//i.test(url.trim())
}

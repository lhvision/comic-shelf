/**
 * @file progress.ts
 * @description 纸间全站进度与百分比计算统一工具集。
 *
 * 核心设计原则（单一真理源）：
 * 1. 未达终态不进位法则（Non-terminal Floor Clamp / 99% 封顶律）：
 *    只要当前任务或数据未达到完全就绪（current < total 或 progress < 1），
 *    百分比显示严格封顶为 99%（采用 Math.floor 向下取整），当且仅当完全就绪时才允许返回 100%；
 * 2. 高精亚像素截断（Subpixel Truncation / 4 位精度规约）：
 *    将 0~1 的原始浮点比率截断保留至 4 位小数（0.0001 精度），避免 IEEE 754 浮点噪点（如 16 位小数）
 *    污染 DOM style 属性与 CSS 变量，同时在 4K（3840px）屏下亚像素误差低于 0.38px。
 */

/**
 * 依据「当前完成量」与「总配额量」计算确定性进度百分比（0~100）。
 *
 * @param current 当前已完成数量（如 cachedPages、completedCount）
 * @param total 目标总量（如 pageCount、totalCount）
 * @returns 0~100 的整数百分比；当 current < total 时严格封顶 99%，绝不虚假进位为 100%
 */
export function calculateProgressPercent(current: number, total: number): number {
  if (typeof total !== 'number' || Number.isNaN(total) || total <= 0) return 0
  if (typeof current !== 'number' || Number.isNaN(current) || current <= 0) return 0
  if (current >= total) return 100
  return Math.min(99, Math.floor((current / total) * 100))
}

/**
 * 依据 0~1 范围的进度比例计算确定性进度百分比（0~100）。
 *
 * @param progress 0~1 浮点进度比率
 * @returns 0~100 的整数百分比；当 progress < 1 时严格封顶 99%
 */
export function calculateFloatPercent(progress: number): number {
  if (typeof progress !== 'number' || Number.isNaN(progress) || progress <= 0) return 0
  if (progress >= 1) return 100
  return Math.min(99, Math.floor(progress * 100))
}

/**
 * 截断浮点数至指定小数位（默认 4 位，对应 0.0001 亚像素精度）。
 *
 * @param value 待处理的原始浮点数
 * @param decimals 保留小数位数，默认 4
 * @returns 截断后的高精浮点数
 */
export function truncateProgressFloat(value: number, decimals = 4): number {
  if (typeof value !== 'number' || Number.isNaN(value)) return 0
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

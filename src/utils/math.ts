/** 纸间数值工具：原生高精求和的渐进增强、集合求和、区间钳位、小数舍入与有限数值校验。 */

/**
 * 对可迭代的数值序列求和。
 * 优先调用原生 Math.sumPrecise，若未实现则回退至简单累加。
 *
 * @param iterable 可迭代的数值集合
 * @returns 累加求和结果
 */
export function sumPrecise(iterable: Iterable<number>): number {
  if (iterable == null) {
    throw new TypeError('sumPrecise: 入参不能为空或未定义')
  }
  const mathObj = Math as unknown as { sumPrecise?: (it: Iterable<number>) => number }
  if (typeof mathObj.sumPrecise === 'function') {
    return mathObj.sumPrecise(iterable)
  }
  let sum = 0
  for (const value of iterable) {
    const num = Number(value)
    if (Number.isNaN(num)) return Number.NaN
    sum += num
  }
  return sum
}

/**
 * 依据指定属性提取函数，对集合项进行求和。
 * 防御性支持传入 null / undefined 空集合，安全返回 0。
 *
 * @template T 集合元素类型
 * @param items 可迭代对象（若为空或未定义直接返回 0）
 * @param iteratee 从元素中提取数值的映射函数
 * @returns 累加求和结果
 */
export function sumBy<T>(
  items: Iterable<T> | null | undefined,
  iteratee: (item: T) => number,
): number {
  if (!items) return 0
  let sum = 0
  for (const item of items) {
    sum += iteratee(item)
  }
  return sum
}

/**
 * 将数值限制在 [min, max] 区间之内（包含边界）。
 * 防御性设计：
 * 1. 若 value 为 NaN，安全回落为 min；
 * 2. 若 min > max，自动交换两者保证区间合法；
 * 3. 若 min 或 max 为 NaN，安全归一为 0。
 *
 * @param value 目标数值
 * @param min 下界
 * @param max 上界
 * @returns 钳位后的有效数值
 */
export function clamp(value: number, min: number, max: number): number {
  const safeMin = typeof min === 'number' && !Number.isNaN(min) ? min : 0
  const safeMax = typeof max === 'number' && !Number.isNaN(max) ? max : 0
  const lower = Math.min(safeMin, safeMax)
  const upper = Math.max(safeMin, safeMax)

  if (typeof value !== 'number' || Number.isNaN(value)) {
    return lower
  }

  return Math.min(Math.max(value, lower), upper)
}

/**
 * 截断/四舍五入数值至指定小数位（默认 0 位）。
 * 采用 Number.EPSILON 符号偏移修正，消除浮点数临界值进位缺陷（如 1.005 保留 2 位小数精确得到 1.01）。
 *
 * @param value 目标数值
 * @param decimals 保留小数位数（>= 0），默认 0
 * @returns 规约后的浮点数值
 */
export function round(value: number, decimals = 0): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 0
  if (decimals <= 0) return Math.round(value)
  const factor = 10 ** decimals
  const offset = (value >= 0 ? 1 : -1) * Number.EPSILON
  return Math.round((value + offset) * factor) / factor
}

/**
 * 防御性将输入转换为有限数值（Finite Number）。
 * 若输入非 number 或为 NaN / ±Infinity，返回指定的 fallback 默认值。
 *
 * @param value 待检查的输入值
 * @param fallback 非法时的兜底数值，默认为 0
 * @returns 合法的有限数值
 */
export function toFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  return fallback
}

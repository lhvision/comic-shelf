/**
 * @file usePaginationFold.ts
 * @description 列表分批增量折叠与平滑滚顶组合式函数。
 *
 * 核心契约：
 * 1. 分批步进展开（loadMore）、全量展开（loadAll）、一键收整（collapse）与重置（reset）；
 * 2. 响应式计算当前展现切片（visibleItems）、剩余项数（remainingCount）与是否可收起（canCollapse）；
 * 3. 收起时自动执行 nextTick + scrollIntoView 平滑回滚至容器顶端，杜绝视口跳跃；
 * 4. 彻底抽离多组件重复手写的分批切片与滚顶样板代码（ComicGrid / PageIndexGrid / ChapterIndex）。
 */

import {
  ref,
  computed,
  nextTick,
  toValue,
  type Ref,
  type ComputedRef,
  type MaybeRefOrGetter,
} from 'vue'

export const DEFAULT_BRAKE_THRESHOLD = 60
export const DEFAULT_LOAD_ALL_CAP = 120

export interface UsePaginationFoldOptions<T> {
  /** 数据源列表 */
  items: MaybeRefOrGetter<T[]>
  /** 外部总条目数（可选，用于服务端分页时覆盖前端切片长度） */
  totalCount?: MaybeRefOrGetter<number | undefined>
  /** 每批增量展示数量（默认 12） */
  step?: MaybeRefOrGetter<number | undefined>
  /** 基础展示与收起基线数量（若未指定则默认为 step） */
  initialStep?: MaybeRefOrGetter<number | undefined>
  /** 初始/恢复可见数量（若未指定则默认为 initialStep 或 step） */
  initialVisibleCount?: MaybeRefOrGetter<number | undefined>
  /** 安全刹车阈值数量（达到该数量时自动暂停流式加载，默认 60） */
  brakeThreshold?: MaybeRefOrGetter<number | undefined>
  /** 全量展开时的默认软封顶数量（可选，若配置且调用 loadAll() 无参时按该步长软封顶递进） */
  loadAllCap?: MaybeRefOrGetter<number | undefined>
  /** 滚动容器 DOM 引用（收起时平滑回滚至该元素顶部） */
  scrollTarget?: Ref<HTMLElement | null>
  /** 展开/收起/重置状态变更后的额外回调（如持久化展开数量） */
  onChange?: (count: number) => void
}

export interface UsePaginationFoldReturn<T> {
  /** 当前已呈现条目数量 */
  visibleCount: Ref<number>
  /** 当前切片展现的数据子集 */
  visibleItems: ComputedRef<T[]>
  /** 剩余未展开的数据条目数 */
  remainingCount: ComputedRef<number>
  /** 是否处于已展开状态（可执行收整） */
  canCollapse: ComputedRef<boolean>
  /** 是否触碰安全刹车保护（达到阈值且仍有剩余项） */
  isBraked: ComputedRef<boolean>
  /** 当前生效的刹车阈值 */
  currentBrakeThreshold: Ref<number>
  /** 再展开一批 */
  loadMore: () => void
  /**
   * 展开全部条目。
   * @param maxCap 可选软封顶数量（默认可选 120）。若总数超量且当前小于封顶，优先铺开至封顶；若已达封顶则递进展开，杜绝极端海量 DOM 卡死。
   */
  loadAll: (maxCap?: number) => void
  /** 释放刹车保护并继续展开 */
  releaseBrake: (additionalCount?: number) => void
  /** 收整回初始批次并平滑滚顶 */
  collapse: () => void
  /** 重置可见数量（列表刷新或筛选变更时调用） */
  reset: (newCount?: number) => void
}

export function usePaginationFold<T>(
  options: UsePaginationFoldOptions<T>,
): UsePaginationFoldReturn<T> {
  const { items, scrollTarget, onChange } = options
  const getStep = () => Math.max(1, toValue(options.step) ?? 12)
  const getBaseCount = () => toValue(options.initialStep) ?? getStep()
  const getInitialCount = () => toValue(options.initialVisibleCount) ?? getBaseCount()
  const getBrakeThreshold = () =>
    Math.max(1, toValue(options.brakeThreshold) ?? DEFAULT_BRAKE_THRESHOLD)

  const visibleCount = ref(getInitialCount())
  const currentBrakeThreshold = ref(getBrakeThreshold())

  const totalLength = computed(() => {
    const extTotal = toValue(options.totalCount)
    if (typeof extTotal === 'number' && extTotal >= 0) {
      return extTotal
    }
    return toValue(items).length
  })

  const visibleItems = computed(() => toValue(items).slice(0, visibleCount.value))
  const remainingCount = computed(() => Math.max(0, totalLength.value - visibleItems.value.length))
  const canCollapse = computed(() => visibleCount.value > getBaseCount())
  const isBraked = computed(
    () => visibleItems.value.length >= currentBrakeThreshold.value && remainingCount.value > 0,
  )

  function loadMore() {
    if (visibleCount.value < totalLength.value) {
      visibleCount.value = Math.min(totalLength.value, visibleCount.value + getStep())
      onChange?.(visibleCount.value)
    }
  }

  function loadAll(maxCap?: number) {
    const effectiveCap =
      typeof maxCap === 'number' && maxCap > 0 ? maxCap : toValue(options.loadAllCap)
    let target = totalLength.value
    if (typeof effectiveCap === 'number' && effectiveCap > 0 && totalLength.value > effectiveCap) {
      if (visibleCount.value < effectiveCap) {
        target = effectiveCap
      } else {
        target = Math.min(totalLength.value, visibleCount.value + effectiveCap)
      }
    }
    visibleCount.value = target
    currentBrakeThreshold.value = Math.max(currentBrakeThreshold.value, target)
    onChange?.(visibleCount.value)
  }

  function releaseBrake(additionalCount = DEFAULT_BRAKE_THRESHOLD) {
    currentBrakeThreshold.value = visibleCount.value + additionalCount
    loadMore()
  }

  function collapse() {
    visibleCount.value = getBaseCount()
    currentBrakeThreshold.value = getBrakeThreshold()
    onChange?.(visibleCount.value)
    void nextTick(() => {
      const el = scrollTarget?.value
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  }

  function reset(newCount?: number) {
    visibleCount.value = newCount ?? getBaseCount()
    currentBrakeThreshold.value = getBrakeThreshold()
    onChange?.(visibleCount.value)
  }

  return {
    visibleCount,
    visibleItems,
    remainingCount,
    canCollapse,
    isBraked,
    currentBrakeThreshold,
    loadMore,
    loadAll,
    releaseBrake,
    collapse,
    reset,
  }
}

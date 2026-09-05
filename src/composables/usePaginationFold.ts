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

export interface UsePaginationFoldOptions<T> {
  /** 数据源列表 */
  items: MaybeRefOrGetter<T[]>
  /** 每批增量展示数量（默认 12） */
  step?: MaybeRefOrGetter<number>
  /** 初始展示数量（若未指定则默认为 step） */
  initialStep?: MaybeRefOrGetter<number>
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
  /** 再展开一批 */
  loadMore: () => void
  /** 展开全部条目 */
  loadAll: () => void
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

  const visibleCount = ref(getBaseCount())

  const totalLength = computed(() => toValue(items).length)
  const visibleItems = computed(() => toValue(items).slice(0, visibleCount.value))
  const remainingCount = computed(() => Math.max(0, totalLength.value - visibleCount.value))
  const canCollapse = computed(() => visibleCount.value > getBaseCount())

  function loadMore() {
    if (visibleCount.value < totalLength.value) {
      visibleCount.value = Math.min(totalLength.value, visibleCount.value + getStep())
      onChange?.(visibleCount.value)
    }
  }

  function loadAll() {
    visibleCount.value = totalLength.value
    onChange?.(visibleCount.value)
  }

  function collapse() {
    visibleCount.value = getBaseCount()
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
  }

  return {
    visibleCount,
    visibleItems,
    remainingCount,
    canCollapse,
    loadMore,
    loadAll,
    collapse,
    reset,
  }
}

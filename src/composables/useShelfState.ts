/**
 * @file useShelfState.ts
 * @description 书架全景上下文记忆与视口锚定组合式函数。
 *
 * 核心职责：
 * 1. 跨路由会话（如书架 ⇄ 详情 ⇄ 阅读器）单例持久保持案头藏书展开批次、
 *    卷末归档专匣开闭态、检索关键词、选中标签、只看喜欢/已读及排序规则；
 * 2. 离开书架视图时记录纵向视口坐标（window.scrollY），返回时用于精确还原；
 * 3. 顶栏显式点击 Logo 或切换来源时支持主动重置书架记忆，回归初态。
 */

import { ref, computed } from 'vue'
import { createGlobalState } from '@vueuse/core'
import type { SortKey } from '@/composables/useLibraryFilter'
import type { ReadingStatus } from '@/types'

export const DEFAULT_SHELF_BATCH = 12

export const useShelfState = createGlobalState(() => {
  /** 离开书架时的垂直滚动偏移量（px） */
  const shelfScrollY = ref(0)
  /** 案头在读藏书当前展开呈现的数量（首屏默认 12 本） */
  const activeUnfoldCount = ref(DEFAULT_SHELF_BATCH)
  /** 卷末归档专匣是否处于展开可见状态 */
  const archiveOpen = ref(false)
  /** 卷末归档专匣内部当前展开呈现的数量 */
  const archiveUnfoldCount = ref(DEFAULT_SHELF_BATCH)
  /** 单网格模式（非分割视图）下当前展开呈现的数量 */
  const unifiedUnfoldCount = ref(DEFAULT_SHELF_BATCH)

  /** 搜索关键词输入内容 */
  const search = ref('')
  /** 当前选中的多标签集合（空数组表示全部） */
  const activeTags = ref<string[]>([])
  /** 向后兼容单标签访问器 */
  const activeTag = computed({
    get: () => activeTags.value[0] || '',
    set: (val: string) => {
      activeTags.value = val ? [val] : []
    },
  })
  /** 是否只看已加入喜欢的藏书 */
  const favoritesOnly = ref(false)
  /** 阅读状态单选维度（all | reading | completed） */
  const readingStatus = ref<ReadingStatus>('all')
  /** 当前选中的排序规则 */
  const sortBy = ref<SortKey>('recent')
  /** 标签筛选条中的「更多标签」抽屉是否处于展开状态 */
  const tagTrayExpanded = ref(false)

  /** 记录当前滚动偏移量 */
  function saveScrollPosition(y: number): void {
    shelfScrollY.value = Math.max(0, y)
  }

  /** 重置滚动记录至顶端 */
  function resetShelfScroll(): void {
    shelfScrollY.value = 0
  }

  /** 重置所有折叠批次与抽屉状态回到初态（12 本） */
  function resetShelfUnfolds(): void {
    activeUnfoldCount.value = DEFAULT_SHELF_BATCH
    archiveOpen.value = false
    archiveUnfoldCount.value = DEFAULT_SHELF_BATCH
    unifiedUnfoldCount.value = DEFAULT_SHELF_BATCH
  }

  /** 重置所有检索与筛选条件 */
  function resetShelfFilters(): void {
    search.value = ''
    activeTags.value = []
    favoritesOnly.value = false
    readingStatus.value = 'all'
    sortBy.value = 'recent'
    tagTrayExpanded.value = false
  }

  /** 显式全新导航时的全量归零重置 */
  function resetAllShelfState(): void {
    resetShelfScroll()
    resetShelfUnfolds()
    resetShelfFilters()
  }

  return {
    shelfScrollY,
    activeUnfoldCount,
    archiveOpen,
    archiveUnfoldCount,
    unifiedUnfoldCount,
    search,
    activeTag,
    activeTags,
    favoritesOnly,
    readingStatus,
    sortBy,
    tagTrayExpanded,
    saveScrollPosition,
    resetShelfScroll,
    resetShelfUnfolds,
    resetShelfFilters,
    resetAllShelfState,
  }
})

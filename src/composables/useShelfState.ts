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

import { computed, ref } from 'vue'
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
  /** 是否只看已加入喜欢的藏书 */
  const favoritesOnly = ref(false)
  /** 阅读状态单选维度（all | reading | completed） */
  const readingStatus = ref<ReadingStatus>('all')
  /** 当前选中的排序规则 */
  const sortBy = ref<SortKey>('recent')
  /** 标签筛选条中的「更多标签」抽屉是否处于展开状态 */
  const tagTrayExpanded = ref(false)

  /** 是否处于非默认筛选态（标签、喜欢、状态、搜索或排序非初态） */
  const hasActiveFilters = computed(
    () =>
      activeTags.value.length > 0 ||
      favoritesOnly.value ||
      readingStatus.value !== 'all' ||
      Boolean(search.value.trim()) ||
      sortBy.value !== 'recent',
  )

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

  /**
   * 从外部路由查询参数中单向恢复书架检索与筛选态（Deep-Link / 页面刷新直达）。
   *
   * @param query 路由 query 对象（通常为 route.query）
   * @returns 是否有任何有效状态被成功恢复
   */
  function hydrateFromQuery(query: Record<string, unknown>): boolean {
    let hydrated = false

    // 1. 恢复多标签 (tags 或 tag)
    const rawTags = query.tags ?? query.tag
    if (typeof rawTags === 'string' && rawTags.trim()) {
      const parsed = rawTags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
      if (parsed.length > 0) {
        activeTags.value = parsed.slice(0, 5)
        hydrated = true
      }
    } else if (Array.isArray(rawTags)) {
      const parsed = rawTags.map((t) => String(t).trim()).filter(Boolean)
      if (parsed.length > 0) {
        activeTags.value = parsed.slice(0, 5)
        hydrated = true
      }
    }

    // 2. 恢复阅读状态 (status: all | reading | completed)
    if (query.status === 'all' || query.status === 'reading' || query.status === 'completed') {
      readingStatus.value = query.status
      hydrated = true
    }

    // 3. 恢复只看喜欢 (favorite / fav: 'true' | '1')
    if (
      query.favorite === 'true' ||
      query.favorite === '1' ||
      query.fav === 'true' ||
      query.fav === '1'
    ) {
      favoritesOnly.value = true
      hydrated = true
    }

    // 4. 恢复搜索词 (q 或 search)
    const rawSearch = query.q ?? query.search
    if (typeof rawSearch === 'string' && rawSearch.trim()) {
      search.value = rawSearch.trim()
      hydrated = true
    }

    // 5. 恢复排序规则 (sort: recent | title | pages | cached)
    if (
      query.sort === 'recent' ||
      query.sort === 'title' ||
      query.sort === 'pages' ||
      query.sort === 'cached'
    ) {
      sortBy.value = query.sort
      hydrated = true
    }

    return hydrated
  }

  /**
   * 构建当前书架筛选维度的深层直达分享 URL。
   *
   * @param baseOriginAndPath 可选的基础路径（默认 window.location.origin + window.location.pathname）
   * @param source 可选的数据源 key（如 'jm', 'picacg', 'local'）
   * @returns 完整的直达链接字符串
   */
  function buildShareUrl(baseOriginAndPath?: string, source?: string): string {
    const base =
      baseOriginAndPath ||
      (typeof window !== 'undefined' ? `${window.location.origin}${window.location.pathname}` : '/')

    const params = new URLSearchParams()
    if (source) {
      params.set('source', source)
    }
    if (search.value.trim()) {
      params.set('q', search.value.trim())
    }
    if (activeTags.value.length > 0) {
      params.set('tags', activeTags.value.join(','))
    }
    if (favoritesOnly.value) {
      params.set('favorite', 'true')
    }
    if (readingStatus.value !== 'all') {
      params.set('status', readingStatus.value)
    }
    if (sortBy.value !== 'recent') {
      params.set('sort', sortBy.value)
    }

    const qs = params.toString()
    return qs ? `${base}?${qs}` : base
  }

  return {
    shelfScrollY,
    activeUnfoldCount,
    archiveOpen,
    archiveUnfoldCount,
    unifiedUnfoldCount,
    search,
    activeTags,
    favoritesOnly,
    readingStatus,
    sortBy,
    tagTrayExpanded,
    hasActiveFilters,
    saveScrollPosition,
    resetShelfScroll,
    resetShelfUnfolds,
    resetShelfFilters,
    resetAllShelfState,
    hydrateFromQuery,
    buildShareUrl,
  }
})

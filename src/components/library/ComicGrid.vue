<script setup lang="ts">
/**
 * 书架网格 —— 骨架屏加载态 / DOM 或 Canvas 卡片 / 空状态。
 * 三种输出形态统一由 loading 与 useCanvas 决定，卡片选择逻辑收敛在此。
 *
 * 48 图预算增量折叠渲染：
 * 每本漫画包含 4 张展示封面（1 主封面 + 3 叠牌封面），默认按 12 本/批（48 张图）
 * 起步展示，末尾通过折叠卡（.shelf-fold-card）提示剩余藏书并支持手动步进/全量展开与随时收起，
 * 彻底避免海量 DOM 阻塞与滚动条无节制失控拉长。
 */
import { ref, computed, watch, nextTick } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import type { LibrarySummary } from '@/types'
import ComicCard from '@/components/ComicCard.vue'
import HtmlCanvasCard from '@/components/HtmlCanvasCard.vue'
import AppIcon from '@/components/AppIcon.vue'
import { liveCacheKey, type LiveCacheState } from '@/stores/library'
import { isCompletedComic } from '@/composables/useLibraryFilter'
import { usePaginationFold } from '@/composables/usePaginationFold'

const props = withDefaults(
  defineProps<{
    loading: boolean
    items: LibrarySummary[]
    /** 是否启用 HTML-in-Canvas 实验卡片 */
    useCanvas: boolean
    /** 书库是否非空（用于空状态区分"没收录"与"没匹配"） */
    hasAnyItems: boolean
    /** 后台缓存任务的实时进度，key 为 `source/source_id` */
    liveCache?: Record<string, LiveCacheState>
    /** 以图搜图的匹配得分与页码，key 为 `source_sourceId` */
    searchMatchMap?: Map<string, { bestMatchPage: number; bestScore: number }>
    /** 每批增量渲染本数，默认 12 本（对应 12 × 4 = 48 张封面图） */
    batchStep?: number
    /** 是否为默认的最近收录排序（用于展示卷末归档分割线） */
    isRecentSort?: boolean
    /** 案头在读藏书初始呈现数量（用于跨路由状态记忆） */
    initialActiveCount?: number
    /** 卷末归档专匣初始呈现数量 */
    initialArchiveCount?: number
    /** 单网格模式初始呈现数量 */
    initialUnifiedCount?: number
    /** 卷末归档专匣初始开闭状态 */
    initialArchiveOpen?: boolean
    /** 服务端是否仍有更多页数据可流式拉取 */
    hasMore?: boolean
    /** 服务端是否正在加载更多 */
    loadingMore?: boolean
    /** 服务端总条目数（用于精确剩余计算） */
    totalCount?: number
    /** 安全刹车阈值（默认 60） */
    brakeThreshold?: number
  }>(),
  {
    batchStep: 12,
    isRecentSort: true,
    initialActiveCount: undefined,
    initialArchiveCount: undefined,
    initialUnifiedCount: undefined,
    initialArchiveOpen: undefined,
    hasMore: false,
    loadingMore: false,
    totalCount: undefined,
    brakeThreshold: 60,
  },
)

const isCompleted = isCompletedComic

// 未读/在读藏书与已读完藏书在最近排序下分离
const activeComics = computed(() =>
  props.isRecentSort ? props.items.filter((item) => !isCompleted(item)) : props.items,
)

const completedComics = computed(() =>
  props.isRecentSort ? props.items.filter((item) => isCompleted(item)) : [],
)

const completedCount = computed(() => completedComics.value.length)

const allCompleted = computed(
  () => props.isRecentSort && props.items.length > 0 && props.items.every(isCompleted),
)

// 双分区模式：在最近收录且非 Canvas 模式下，同时存在未读和已读书籍时启用
const isSplitMode = computed(
  () =>
    props.isRecentSort &&
    !props.useCanvas &&
    activeComics.value.length > 0 &&
    completedComics.value.length > 0,
)

const emit = defineEmits<{
  favoriteToggled: [source: string, sourceId: string, favorite: boolean]
  'update:activeCount': [count: number]
  'update:archiveCount': [count: number]
  'update:unifiedCount': [count: number]
  'update:archiveOpen': [open: boolean]
  loadMore: []
  loadAll: []
}>()

const keyOf = (source: string, sourceId: string) => liveCacheKey(source, sourceId)

const gridWrapEl = ref<HTMLElement | null>(null)
const archiveDrawerEl = ref<HTMLElement | null>(null)
const activeSentinelEl = ref<HTMLElement | null>(null)
const unifiedSentinelEl = ref<HTMLElement | null>(null)

// 1. 未读区分批状态
const {
  visibleItems: visibleActiveItems,
  remainingCount: remainingActiveCount,
  canCollapse: canCollapseActiveRaw,
  visibleCount: activeVisibleCount,
  isBraked: isBrakedActive,
  loadMore: loadMoreActive,
  loadAll: loadAllActive,
  releaseBrake: releaseBrakeActive,
  collapse: collapseActive,
  reset: resetActive,
} = usePaginationFold({
  items: activeComics,
  step: () => props.batchStep,
  initialVisibleCount: () => props.initialActiveCount,
  brakeThreshold: () => props.brakeThreshold,
  totalCount: () => (isSplitMode.value ? undefined : props.totalCount),
  scrollTarget: gridWrapEl,
  onChange: (count) => emit('update:activeCount', count),
})
const canCollapseActive = computed(() => !props.useCanvas && canCollapseActiveRaw.value)

// 2. 卷末归档专匣状态
const archiveOpen = ref(props.initialArchiveOpen ?? false)
watch(
  () => props.initialArchiveOpen,
  (val) => {
    if (val !== undefined && val !== archiveOpen.value) {
      archiveOpen.value = val
    }
  },
)

function toggleArchive() {
  archiveOpen.value = !archiveOpen.value
  emit('update:archiveOpen', archiveOpen.value)
}

const {
  visibleItems: visibleArchiveItems,
  remainingCount: remainingArchiveCount,
  canCollapse: canCollapseArchive,
  visibleCount: archiveVisibleCount,
  loadMore: loadMoreArchive,
  loadAll: loadAllArchive,
  collapse: collapseArchive,
  reset: resetArchive,
} = usePaginationFold({
  items: completedComics,
  step: () => props.batchStep,
  initialVisibleCount: () => props.initialArchiveCount,
  brakeThreshold: () => props.brakeThreshold,
  scrollTarget: archiveDrawerEl,
  onChange: (count) => emit('update:archiveCount', count),
})

// 3. 全局单网格（非 splitMode 时：如全已读、全未读、非最近收录、Canvas 模式）
const {
  visibleItems: rawVisibleItems,
  remainingCount,
  canCollapse: canCollapseRaw,
  visibleCount: unifiedVisibleCount,
  isBraked: isBrakedUnified,
  loadMore,
  loadAll,
  releaseBrake: releaseBrakeUnified,
  collapse,
  reset: resetUnified,
} = usePaginationFold({
  items: () => props.items,
  step: () => props.batchStep,
  initialVisibleCount: () => props.initialUnifiedCount,
  brakeThreshold: () => props.brakeThreshold,
  totalCount: () => props.totalCount,
  scrollTarget: gridWrapEl,
  onChange: (count) => emit('update:unifiedCount', count),
})

useIntersectionObserver(
  activeSentinelEl,
  ([entry]) => {
    if (entry?.isIntersecting && !props.loading && !props.loadingMore) {
      triggerActiveStreamLoad()
    }
  },
  { rootMargin: '300px 0px' },
)

useIntersectionObserver(
  unifiedSentinelEl,
  ([entry]) => {
    if (entry?.isIntersecting && !props.loading && !props.loadingMore) {
      triggerUnifiedStreamLoad()
    }
  },
  { rootMargin: '300px 0px' },
)

function triggerActiveStreamLoad() {
  if (isBrakedActive.value) return

  if (visibleActiveItems.value.length < activeComics.value.length) {
    loadMoreActive()
  } else if (props.hasMore) {
    emit('loadMore')
  }
}

function triggerUnifiedStreamLoad() {
  if (isBrakedUnified.value) return

  if (visibleItems.value.length < props.items.length) {
    loadMore()
  } else if (props.hasMore) {
    emit('loadMore')
  }
}

const isExpandingAllActive = ref(false)
const isExpandingAllUnified = ref(false)

function onCollapseActive() {
  isExpandingAllActive.value = false
  collapseActive()
}

function onCollapseUnified() {
  isExpandingAllUnified.value = false
  collapse()
}

function handleContinueActive() {
  if (isBrakedActive.value) {
    releaseBrakeActive(props.batchStep * 2)
  } else {
    loadMoreActive()
  }
  if (visibleActiveItems.value.length >= activeComics.value.length && props.hasMore) {
    emit('loadMore')
  }
}

function handleLoadAllActive() {
  isExpandingAllActive.value = true
  loadAllActive()
  if (props.hasMore) {
    emit('loadAll')
  }
}

function handleContinueUnified() {
  if (isBrakedUnified.value) {
    releaseBrakeUnified(props.batchStep * 2)
  } else {
    loadMore()
  }
  if (visibleItems.value.length >= props.items.length && props.hasMore) {
    emit('loadMore')
  }
}

function handleLoadAllUnified() {
  isExpandingAllUnified.value = true
  loadAll()
  if (props.hasMore) {
    emit('loadAll')
  }
}

const visibleItems = computed(() => {
  if (props.useCanvas) return props.items
  return rawVisibleItems.value
})
const canCollapse = computed(() => !props.useCanvas && canCollapseRaw.value)

watch(
  () => props.initialActiveCount,
  (count) => {
    if (count !== undefined && count !== activeVisibleCount.value) {
      resetActive(count)
    }
  },
)
watch(
  () => props.initialArchiveCount,
  (count) => {
    if (count !== undefined && count !== archiveVisibleCount.value) {
      resetArchive(count)
    }
  },
)
watch(
  () => props.initialUnifiedCount,
  (count) => {
    if (count !== undefined && count !== unifiedVisibleCount.value) {
      resetUnified(count)
    }
  },
)

// 当数据源发生变化时：
// 1. 若为增量分页加载（append），自动向外顺延展现新拉取的批次，解决第二页加载后仍不渲染问题；
// 2. 若为全新查询/筛选变更，收拢全量展开态并重置可见数；
// 3. 若为原地状态更新且当前可见数越界，进行安全钳制。
watch(
  () => props.items,
  (newItems, oldItems = []) => {
    const isAppend =
      oldItems.length > 0 &&
      newItems.length > oldItems.length &&
      newItems[0]?.source === oldItems[0]?.source &&
      newItems[0]?.source_id === oldItems[0]?.source_id

    if (isAppend) {
      const oldActiveCount = oldItems.filter((i) => !isCompleted(i)).length
      if (isExpandingAllActive.value) {
        loadAllActive()
      } else if (activeVisibleCount.value >= oldActiveCount) {
        // 用户此前已滚动至未读藏书末尾，新一页到达后自动向外展开下一批
        activeVisibleCount.value = Math.min(
          activeComics.value.length,
          activeVisibleCount.value + props.batchStep,
        )
        emit('update:activeCount', activeVisibleCount.value)
      }

      if (isExpandingAllUnified.value) {
        loadAll()
      } else if (unifiedVisibleCount.value >= oldItems.length) {
        // 单网格模式下同理
        unifiedVisibleCount.value = Math.min(
          newItems.length,
          unifiedVisibleCount.value + props.batchStep,
        )
        emit('update:unifiedCount', unifiedVisibleCount.value)
      }
    } else {
      isExpandingAllActive.value = false
      isExpandingAllUnified.value = false
      if (props.initialActiveCount === undefined) {
        resetActive()
        resetArchive()
        resetUnified()
      } else {
        if (activeVisibleCount.value > activeComics.value.length) {
          resetActive(Math.max(props.batchStep, activeComics.value.length))
        }
        if (archiveVisibleCount.value > completedComics.value.length) {
          resetArchive(Math.max(props.batchStep, completedComics.value.length))
        }
        if (unifiedVisibleCount.value > newItems.length) {
          resetUnified(Math.max(props.batchStep, newItems.length))
        }
      }
    }
  },
)

watch(
  () => props.loadingMore,
  (loadingMore, prevLoadingMore) => {
    if (prevLoadingMore && !loadingMore) {
      if (!props.hasMore) {
        isExpandingAllActive.value = false
        isExpandingAllUnified.value = false
      }
      // 流式加载结束后若触底桩仍位于可视区域内，自动触发下一波次
      void nextTick(() => {
        if (isSplitMode.value && activeSentinelEl.value) {
          const rect = activeSentinelEl.value.getBoundingClientRect()
          if (rect.top <= window.innerHeight + 300 && rect.bottom >= 0) {
            triggerActiveStreamLoad()
          }
        } else if (!isSplitMode.value && unifiedSentinelEl.value) {
          const rect = unifiedSentinelEl.value.getBoundingClientRect()
          if (rect.top <= window.innerHeight + 300 && rect.bottom >= 0) {
            triggerUnifiedStreamLoad()
          }
        }
      })
    }
  },
)
</script>

<template>
  <div v-if="loading" class="comic-grid" aria-label="加载中">
    <div v-for="index in 6" :key="index" class="skeleton-card">
      <div class="skeleton cover-skeleton" />
      <div class="skeleton line-skeleton" />
      <div class="skeleton line-skeleton short" />
    </div>
  </div>

  <div v-else-if="items.length" ref="gridWrapEl" class="comic-grid-wrap">
    <!-- 1. 双分区架构：未读在读书架 + 卷末典藏抽屉 -->
    <template v-if="isSplitMode">
      <!-- 案头在读区 -->
      <TransitionGroup tag="div" name="shelf-card" class="comic-grid active-shelf-grid">
        <ComicCard
          v-for="item in visibleActiveItems"
          :key="`item-${item.source}/${item.source_id}`"
          :comic="item"
          :cache="liveCache?.[keyOf(item.source, item.source_id)]"
          :search-match="searchMatchMap?.get(`${item.source}_${item.source_id}`)"
          @favorite-toggled="
            (source, sourceId, value) => emit('favoriteToggled', source, sourceId, value)
          "
        />

        <!-- 流式加载触底侦测桩 -->
        <div
          ref="activeSentinelEl"
          key="active-stream-sentinel"
          class="stream-sentinel"
          aria-hidden="true"
        />

        <!-- 未读尾格折叠卡 -->
        <div
          v-if="remainingActiveCount > 0 || hasMore"
          key="active-fold-card"
          class="shelf-fold-card surface"
          :class="{ 'is-braked': isBrakedActive }"
          role="region"
          aria-label="未读藏书折叠收纳卡"
        >
          <div class="fold-card-body">
            <div class="fold-badge-wrap">
              <AppIcon name="book-open" size="sm" class="fold-badge-icon" />
              <span class="fold-badge-stamp">
                {{ remainingActiveCount > 0 ? `+${remainingActiveCount} 本未读` : '后续藏书' }}
              </span>
            </div>
            <h4 class="fold-card-title">
              {{ isBrakedActive ? '流式加载已触发安全刹车' : '未读藏书已收纳' }}
            </h4>
            <p class="fold-card-hint">
              {{
                isBrakedActive
                  ? `案头已连续呈现 ${visibleActiveItems.length} 本，已达 60 本安全阈值，暂停自动滚动加载以节约设备内存。`
                  : remainingActiveCount > 0
                    ? `案头展示前 ${visibleActiveItems.length} 本，还有 ${remainingActiveCount} 本未读已折叠。`
                    : `案头展示前 ${visibleActiveItems.length} 本，滚动或点击继续加载后续藏书。`
              }}
            </p>
            <div class="fold-card-actions">
              <button
                class="btn btn-primary btn-small"
                type="button"
                @click.prevent="handleContinueActive"
              >
                <AppIcon name="chevron-down" size="xs" />
                {{
                  isBrakedActive
                    ? '继续向下探索 24 本'
                    : `再展开 ${Math.min(batchStep, remainingActiveCount || batchStep)} 本`
                }}
              </button>
              <button
                class="btn btn-ghost btn-small"
                type="button"
                @click.prevent="handleLoadAllActive"
              >
                <AppIcon name="book-open" size="xs" />
                展开全部未读
              </button>
              <button
                v-if="canCollapseActive"
                class="btn btn-ghost btn-small"
                type="button"
                @click.prevent="onCollapseActive"
              >
                <AppIcon name="chevron-up" size="xs" />
                收整未读
              </button>
            </div>
          </div>
        </div>
      </TransitionGroup>

      <div v-if="loadingMore" class="stream-loading-bar" role="status">
        <AppIcon name="refresh" size="xs" class="stream-loading-spinner" />
        <span>正在载入后续藏书...</span>
      </div>

      <!-- 未读全量展开后的收整条 -->
      <div
        v-if="canCollapseActive && remainingActiveCount === 0 && !hasMore"
        class="shelf-sentinel surface"
      >
        <div class="sentinel-info">
          <AppIcon name="book-open" size="sm" class="sentinel-icon" />
          <span class="sentinel-note">
            已呈现 {{ visibleActiveItems.length }} /
            {{ activeComics.length }} 本未读藏书（全部未读已展开）
          </span>
        </div>
        <div class="sentinel-actions">
          <button class="btn btn-ghost btn-small" type="button" @click.prevent="onCollapseActive">
            <AppIcon name="chevron-up" size="xs" />
            收整未读
          </button>
        </div>
      </div>

      <!-- 卷末归档专匣（Archive Drawer）：基于 interpolate-size: allow-keywords 的平滑折叠抽屉 -->
      <section
        ref="archiveDrawerEl"
        class="shelf-archive-drawer"
        :class="{ 'is-open': archiveOpen }"
        aria-label="卷末归档专匣"
      >
        <button
          class="archive-drawer-header surface"
          type="button"
          :aria-expanded="archiveOpen"
          aria-label="切换卷末归档抽屉展开状态"
          @click="toggleArchive"
        >
          <div class="archive-drawer-title">
            <AppIcon name="archive" size="sm" class="archive-title-icon" />
            <span class="archive-title-text">
              卷末归档 · 已读完 {{ completedComics.length }} 本
            </span>
            <span class="archive-title-hint">
              {{ archiveOpen ? '点击收拢典藏抽屉' : '点击拉开典藏抽屉' }}
            </span>
          </div>
          <div class="archive-toggle-indicator" aria-hidden="true">
            <span class="archive-toggle-label">{{ archiveOpen ? '收拢归档' : '展开归档' }}</span>
            <AppIcon :name="archiveOpen ? 'chevron-up' : 'chevron-down'" size="xs" />
          </div>
        </button>

        <div class="archive-drawer-body" :inert="!archiveOpen">
          <div class="archive-drawer-inner">
            <TransitionGroup tag="div" name="shelf-card" class="comic-grid archive-shelf-grid">
              <ComicCard
                v-for="item in visibleArchiveItems"
                :key="`archive-${item.source}/${item.source_id}`"
                :comic="item"
                :cache="liveCache?.[keyOf(item.source, item.source_id)]"
                @favorite-toggled="
                  (source, sourceId, value) => emit('favoriteToggled', source, sourceId, value)
                "
              />

              <!-- 归档尾格折叠卡 -->
              <div
                v-if="remainingArchiveCount > 0"
                key="archive-fold-card"
                class="shelf-fold-card shelf-fold-card--archive surface"
                role="region"
                aria-label="已读典藏折叠收纳卡"
              >
                <div class="fold-card-body">
                  <div class="fold-badge-wrap">
                    <AppIcon name="archive" size="sm" class="fold-badge-icon" />
                    <span class="fold-badge-stamp">+{{ remainingArchiveCount }} 本已读</span>
                  </div>
                  <h4 class="fold-card-title">已读典藏已收纳</h4>
                  <p class="fold-card-hint">
                    归档展示前 {{ visibleArchiveItems.length }} 本，还有
                    {{ remainingArchiveCount }} 本已读已折叠。
                  </p>
                  <div class="fold-card-actions">
                    <button
                      class="btn btn-primary btn-small"
                      type="button"
                      @click.prevent="loadMoreArchive"
                    >
                      <AppIcon name="chevron-down" size="xs" />
                      再展开 {{ Math.min(batchStep, remainingArchiveCount) }} 本
                    </button>
                    <button
                      class="btn btn-ghost btn-small"
                      type="button"
                      @click.prevent="loadAllArchive"
                    >
                      <AppIcon name="book-open" size="xs" />
                      展开全部已读
                    </button>
                    <button
                      v-if="canCollapseArchive"
                      class="btn btn-ghost btn-small"
                      type="button"
                      @click.prevent="collapseArchive"
                    >
                      <AppIcon name="chevron-up" size="xs" />
                      收整已读
                    </button>
                  </div>
                </div>
              </div>
            </TransitionGroup>

            <!-- 归档全量展开后的收整条 -->
            <div
              v-if="canCollapseArchive && remainingArchiveCount === 0"
              class="shelf-sentinel surface"
            >
              <div class="sentinel-info">
                <AppIcon name="archive" size="sm" class="sentinel-icon" />
                <span class="sentinel-note">
                  已呈现 {{ visibleArchiveItems.length }} /
                  {{ completedComics.length }} 本已读典藏（全归档已展开）
                </span>
              </div>
              <div class="sentinel-actions">
                <button
                  class="btn btn-ghost btn-small"
                  type="button"
                  @click.prevent="collapseArchive"
                >
                  <AppIcon name="chevron-up" size="xs" />
                  收整已读
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <!-- 2. 单网格退化模式（全已读、全未读、自定义排序或 Canvas 模式） -->
    <template v-else>
      <div v-if="allCompleted" class="shelf-archive-divider" role="separator" aria-label="典藏归档">
        <span class="archive-divider-line" />
        <span class="archive-divider-badge">
          <AppIcon name="archive" size="sm" />
          典藏归档 · 全部已翻阅（{{ completedCount }} 本）
        </span>
        <span class="archive-divider-line" />
      </div>

      <div v-if="useCanvas" class="comic-grid">
        <HtmlCanvasCard
          v-for="item in visibleItems"
          :key="`canvas-${item.source}/${item.source_id}`"
          :comic="item"
          :enabled="true"
          :cache="liveCache?.[keyOf(item.source, item.source_id)]"
          @favorite-toggled="
            (source, sourceId, value) => emit('favoriteToggled', source, sourceId, value)
          "
        />
      </div>

      <TransitionGroup v-else tag="div" name="shelf-card" class="comic-grid">
        <ComicCard
          v-for="item in visibleItems"
          :key="`item-${item.source}/${item.source_id}`"
          :comic="item"
          :cache="liveCache?.[keyOf(item.source, item.source_id)]"
          :search-match="searchMatchMap?.get(`${item.source}_${item.source_id}`)"
          @favorite-toggled="
            (source, sourceId, value) => emit('favoriteToggled', source, sourceId, value)
          "
        />

        <!-- 流式加载触底侦测桩 -->
        <div
          ref="unifiedSentinelEl"
          key="unified-stream-sentinel"
          class="stream-sentinel"
          aria-hidden="true"
        />

        <!-- 尾格折叠卡 -->
        <div
          v-if="remainingCount > 0 || hasMore"
          key="unified-fold-card"
          class="shelf-fold-card surface"
          :class="{ 'is-braked': isBrakedUnified }"
          role="region"
          aria-label="藏书折叠收纳卡"
        >
          <div class="fold-card-body">
            <div class="fold-badge-wrap">
              <AppIcon name="archive" size="sm" class="fold-badge-icon" />
              <span class="fold-badge-stamp">
                {{ remainingCount > 0 ? `+${remainingCount} 本` : '后续藏书' }}
              </span>
            </div>
            <h4 class="fold-card-title">
              {{ isBrakedUnified ? '流式加载已触发安全刹车' : '后续藏书已收纳' }}
            </h4>
            <p class="fold-card-hint">
              {{
                isBrakedUnified
                  ? `当前已连续呈现 ${visibleItems.length} 本，已达 60 本安全阈值，暂停自动滚动加载以节约设备内存。`
                  : remainingCount > 0
                    ? `当前展示前 ${visibleItems.length} 本，还有 ${remainingCount} 本已折叠。`
                    : `当前展示前 ${visibleItems.length} 本，滚动或点击继续加载后续藏书。`
              }}
            </p>
            <div class="fold-card-actions">
              <button
                class="btn btn-primary btn-small"
                type="button"
                @click.prevent="handleContinueUnified"
              >
                <AppIcon name="chevron-down" size="xs" />
                {{
                  isBrakedUnified
                    ? '继续向下探索 24 本'
                    : `再展开 ${Math.min(batchStep, remainingCount || batchStep)} 本`
                }}
              </button>
              <button
                class="btn btn-ghost btn-small"
                type="button"
                @click.prevent="handleLoadAllUnified"
              >
                <AppIcon name="book-open" size="xs" />
                展开全部
              </button>
              <button
                v-if="canCollapse"
                class="btn btn-ghost btn-small"
                type="button"
                @click.prevent="onCollapseUnified"
              >
                <AppIcon name="chevron-up" size="xs" />
                收整书架
              </button>
            </div>
          </div>
        </div>
      </TransitionGroup>

      <div v-if="loadingMore" class="stream-loading-bar" role="status">
        <AppIcon name="refresh" size="xs" class="stream-loading-spinner" />
        <span>正在载入后续藏书...</span>
      </div>

      <!-- 底部收整控制条 -->
      <div
        v-if="!useCanvas && canCollapse && remainingCount === 0 && !hasMore"
        class="shelf-sentinel surface"
      >
        <div class="sentinel-info">
          <AppIcon name="archive" size="sm" class="sentinel-icon" />
          <span class="sentinel-note">
            已呈现 {{ visibleItems.length }} / {{ items.length }} 本（全架藏书已展开）
          </span>
        </div>
        <div class="sentinel-actions">
          <button class="btn btn-ghost btn-small" type="button" @click.prevent="onCollapseUnified">
            <AppIcon name="chevron-up" size="xs" />
            收整书架
          </button>
        </div>
      </div>
    </template>
  </div>

  <div v-else class="empty-shelf surface">
    <AppIcon name="archive" size="xl" class="empty-mark-icon" aria-hidden="true" />
    <h3>{{ hasAnyItems ? '没有匹配的本子' : '书架还是空的' }}</h3>
    <p>
      {{
        hasAnyItems
          ? '换个关键词或清除标签筛选。'
          : '从上方入口收录第一部画卷，封面会用前几页自动生成。'
      }}
    </p>
  </div>
</template>

<style scoped>
.comic-grid-wrap {
  display: flex;
  flex-direction: column;
}

.comic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(15rem, 100%), 1fr));
  gap: var(--space-5);
  padding-top: var(--space-5);
}

.shelf-archive-divider {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-6) 0 var(--space-2);
}

.archive-divider-line {
  flex: 1;
  height: 1px;
  background: var(--line);
}

.archive-divider-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: color-mix(in oklab, var(--paper-0) 70%, var(--paper-1));
  border: 1px solid var(--line);
  border-radius: var(--radius-full);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  letter-spacing: 0.04em;
  box-shadow: var(--shadow-1);
}

.shelf-fold-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: var(--space-6) var(--space-4);
  border-radius: var(--radius-3);
  border: 1px dashed color-mix(in oklab, var(--accent) 35%, var(--line-strong));
  background: color-mix(in oklab, var(--paper-1) 80%, transparent);
  text-align: center;
  height: 100%;
  min-height: 26rem;
  box-shadow: var(--shadow-1);
  transition:
    border-color var(--duration-2) var(--ease-out),
    background-color var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out);
}

.shelf-fold-card:hover {
  border-color: var(--accent);
  background: var(--paper-1);
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
}

.fold-card-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  max-width: 13rem;
}

.fold-badge-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  background: color-mix(in oklab, var(--accent) 12%, transparent);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-pill);
  border: 1px solid color-mix(in oklab, var(--accent) 25%, transparent);
}

.fold-badge-icon {
  color: var(--accent);
}

.fold-badge-stamp {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--accent);
}

.fold-card-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--ink-0);
  margin: 0;
}

.fold-card-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
  line-height: var(--leading-relaxed);
}

.fold-card-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  margin-top: var(--space-2);
}

.shelf-sentinel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
}

.sentinel-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sentinel-icon {
  color: var(--accent);
}

.sentinel-note {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
}

.sentinel-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

@media (max-width: 640px) {
  .shelf-sentinel {
    flex-direction: column;
    align-items: stretch;
  }

  .sentinel-actions {
    justify-content: flex-end;
  }

  .fold-card-actions .btn,
  .sentinel-actions .btn {
    min-height: 44px;
  }
}

.skeleton-card {
  display: grid;
  gap: var(--space-3);
}

.cover-skeleton {
  aspect-ratio: 3 / 4.15;
}

.line-skeleton {
  height: 1rem;
}

.line-skeleton.short {
  width: 58%;
}

.empty-shelf {
  display: grid;
  justify-items: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
  padding: var(--space-10) var(--space-5);
  text-align: center;
  color: var(--ink-1);
}

.empty-mark-icon {
  font-size: 3rem;
  color: var(--ink-2);
}

/* 卷末归档专匣（Archive Drawer） */
.shelf-archive-drawer {
  margin-top: var(--space-8);
  border: 1px solid var(--line);
  border-radius: var(--radius-3);
  background: color-mix(in oklab, var(--paper-0) 65%, var(--paper-1));
  overflow: clip;
  box-shadow: var(--shadow-1);
  transition:
    border-color var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out);
}

.shelf-archive-drawer:hover {
  border-color: var(--line-strong);
}

.archive-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  cursor: pointer;
  user-select: none;
  background: color-mix(in oklab, var(--paper-0) 88%, var(--paper-1));
  border: none;
  border-bottom: 1px solid transparent;
  text-align: left;
  font: inherit;
  color: inherit;
  transition:
    background-color var(--duration-1) var(--ease-out),
    border-color var(--duration-2) var(--ease-out);
}

.shelf-archive-drawer.is-open .archive-drawer-header {
  border-bottom-color: var(--line);
}

.archive-drawer-header:hover {
  background: color-mix(in oklab, var(--paper-2) 45%, var(--paper-0));
}

.archive-drawer-header:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.archive-drawer-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.archive-title-icon {
  color: var(--accent);
  flex-shrink: 0;
}

.archive-title-text {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-0);
  letter-spacing: 0.02em;
}

.archive-title-hint {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

@media (max-width: 640px) {
  .archive-title-hint {
    display: none;
  }
}

.archive-toggle-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  font-size: var(--text-xs);
  color: var(--ink-2);
  pointer-events: none;
}

/* 抽屉平滑尺寸插值：基于 interpolate-size: allow-keywords */
.archive-drawer-body {
  interpolate-size: allow-keywords;
  height: 0;
  overflow: clip;
  opacity: 0;
  visibility: hidden;
  transition:
    height var(--duration-3) var(--ease-spring),
    opacity var(--duration-2) var(--ease-out),
    visibility var(--duration-2) var(--ease-out);
}

.shelf-archive-drawer.is-open .archive-drawer-body {
  height: auto;
  opacity: 1;
  visibility: visible;
}

@supports not (interpolate-size: allow-keywords) {
  .archive-drawer-body {
    display: grid;
    grid-template-rows: 0fr;
    transition:
      grid-template-rows var(--duration-3) var(--ease-spring),
      opacity var(--duration-2) var(--ease-out),
      visibility var(--duration-2) var(--ease-out);
    height: auto;
  }
  .shelf-archive-drawer.is-open .archive-drawer-body {
    grid-template-rows: 1fr;
  }
  .archive-drawer-inner {
    min-height: 0;
    overflow: clip;
  }
}

.archive-drawer-inner {
  padding: 0 var(--space-5) var(--space-6);
}

.archive-shelf-grid :deep(.comic-card) {
  opacity: 0.88;
  filter: grayscale(0.08);
  transition:
    opacity var(--duration-2) var(--ease-out),
    filter var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out);
}

.archive-shelf-grid :deep(.comic-card:hover),
.archive-shelf-grid :deep(.comic-card:focus-within) {
  opacity: 1;
  filter: none;
}

/* 卡片微动与进场动画 */
.shelf-card-enter-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-spring);
}

.shelf-card-enter-from {
  opacity: 0;
  transform: translateY(14px) scale(0.98);
}

.shelf-card-leave-active {
  transition:
    opacity var(--duration-1) var(--ease-out),
    transform var(--duration-1) var(--ease-out);
}

.shelf-card-leave-to {
  opacity: 0;
  transform: scale(0.96);
}

.shelf-card-move {
  transition: transform var(--duration-2) var(--ease-out);
}

/* 流式加载触底侦测桩与加载指示条 */
.stream-sentinel {
  width: 100%;
  height: 1px;
  pointer-events: none;
  opacity: 0;
  grid-column: 1 / -1;
}

.stream-loading-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) 0 var(--space-4);
  color: var(--ink-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  grid-column: 1 / -1;
}

.stream-loading-spinner {
  animation: stream-spin 1.2s linear infinite;
}

@keyframes stream-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.shelf-fold-card.is-braked {
  border-color: color-mix(in oklab, var(--accent) 35%, var(--line));
  box-shadow: var(--shadow-1);
}

@media (prefers-reduced-motion: reduce) {
  .shelf-card-enter-active,
  .shelf-card-leave-active,
  .shelf-card-move,
  .archive-drawer-body,
  .stream-loading-spinner {
    transition: none !important;
    animation: none !important;
  }
}
</style>

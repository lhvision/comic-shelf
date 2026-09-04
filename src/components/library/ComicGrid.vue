<script setup lang="ts">
/**
 * 书架网格 —— 骨架屏加载态 / DOM 或 Canvas 卡片 / 空状态。
 * 三种输出形态统一由 loading 与 useCanvas 决定，卡片选择逻辑收敛在此。
 *
 * 48 图预算增量渲染：
 * 每本漫画包含 4 张展示封面（1 主封面 + 3 叠牌封面），默认按 12 本/批（48 张图）
 * 增量渲染，使用 useIntersectionObserver 监听底部哨兵平滑展开，彻底避免海量 DOM 阻塞
 * 与 CSS contain: paint 的生硬裁剪。
 */
import { ref, computed, watch } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import type { LibrarySummary } from '@/types'
import ComicCard from '@/components/ComicCard.vue'
import HtmlCanvasCard from '@/components/HtmlCanvasCard.vue'
import AppIcon from '@/components/AppIcon.vue'
import { liveCacheKey, type LiveCacheState } from '@/stores/library'

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
  }>(),
  {
    batchStep: 12,
    isRecentSort: true,
  },
)

const completedCount = computed(
  () =>
    props.items.filter((item) => (item.last_page ?? 0) >= item.page_count && item.page_count > 0)
      .length,
)

const allCompleted = computed(
  () =>
    props.isRecentSort &&
    props.items.length > 0 &&
    props.items.every((item) => (item.last_page ?? 0) >= item.page_count && item.page_count > 0),
)

const firstCompletedIndex = computed(() => {
  if (!props.isRecentSort) return -1
  if (allCompleted.value) return 0
  const activeExists = props.items.some((item) => (item.last_page ?? 0) < item.page_count)
  if (!activeExists) return -1
  return props.items.findIndex(
    (item) => (item.last_page ?? 0) >= item.page_count && item.page_count > 0,
  )
})

const emit = defineEmits<{
  favoriteToggled: [source: string, sourceId: string, favorite: boolean]
}>()

const keyOf = (source: string, sourceId: string) => liveCacheKey(source, sourceId)

// 增量加载状态：每本 4 张封面图，初始与步长均为 batchStep（12 本 / 48 图）
const visibleCount = ref(props.batchStep)

// 当 items 列表发生变更（如切换筛选/排序/检索）时，重置可见数量为初始批次
watch(
  () => props.items,
  () => {
    visibleCount.value = props.batchStep
  },
)

const visibleItems = computed(() => {
  // Canvas 模式下无需分批（单 Canvas 自身即极度轻量）；DOM 模式按 visibleCount 截取
  if (props.useCanvas) return props.items
  return props.items.slice(0, visibleCount.value)
})

const remainingCount = computed(() => Math.max(0, props.items.length - visibleCount.value))

function loadMore() {
  if (visibleCount.value < props.items.length) {
    visibleCount.value = Math.min(props.items.length, visibleCount.value + props.batchStep)
  }
}

const loadMoreTrigger = ref<HTMLElement | null>(null)

useIntersectionObserver(
  loadMoreTrigger,
  (entries) => {
    if (entries[0]?.isIntersecting) {
      loadMore()
    }
  },
  { rootMargin: '600px 0px' },
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

  <div v-else-if="items.length" class="comic-grid-wrap">
    <div class="comic-grid">
      <template
        v-for="(item, index) in visibleItems"
        :key="`item-${item.source}/${item.source_id}`"
      >
        <div
          v-if="index === firstCompletedIndex"
          class="shelf-archive-divider"
          role="separator"
          aria-label="卷末归档"
        >
          <span class="archive-divider-line" />
          <span class="archive-divider-badge">
            <AppIcon name="archive" size="sm" />
            {{
              allCompleted
                ? `典藏归档 · 全部已翻阅（${completedCount} 本）`
                : `卷末归档 · 已读完 ${completedCount} 本`
            }}
          </span>
          <span class="archive-divider-line" />
        </div>

        <HtmlCanvasCard
          v-if="useCanvas"
          :comic="item"
          :enabled="true"
          :cache="liveCache?.[keyOf(item.source, item.source_id)]"
          @favorite-toggled="
            (source, sourceId, value) => emit('favoriteToggled', source, sourceId, value)
          "
        />
        <ComicCard
          v-else
          :comic="item"
          :cache="liveCache?.[keyOf(item.source, item.source_id)]"
          :search-match="searchMatchMap?.get(`${item.source}_${item.source_id}`)"
          @favorite-toggled="
            (source, sourceId, value) => emit('favoriteToggled', source, sourceId, value)
          "
        />
      </template>
    </div>

    <div v-if="!useCanvas && remainingCount > 0" ref="loadMoreTrigger" class="shelf-sentinel">
      <p class="sentinel-note">
        已呈现 {{ visibleItems.length }} / {{ items.length }} 本（余 {{ remainingCount }} 本未展开）
      </p>
      <button class="btn btn-ghost btn-small" type="button" @click.prevent="loadMore">
        展开后 {{ Math.min(batchStep, remainingCount) }} 本
      </button>
    </div>
  </div>

  <div v-else class="empty-shelf surface">
    <AppIcon name="archive" size="xl" class="empty-mark-icon" aria-hidden="true" />
    <h3>{{ hasAnyItems ? '没有匹配的本子' : '书架还是空的' }}</h3>
    <p>
      {{
        hasAnyItems
          ? '换个关键词或清除标签筛选。'
          : '从上面的输入框收录第一本禁漫车，封面会用首页几张自动生成。'
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

.shelf-sentinel {
  display: grid;
  justify-items: center;
  gap: var(--space-2);
  margin-top: var(--space-6);
  padding: var(--space-4);
  border: 1px dashed var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0) 50%, transparent);
}

.sentinel-note {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
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
</style>

<script setup lang="ts">
/**
 * 书架网格 —— 骨架屏加载态 / DOM 或 Canvas 卡片 / 空状态。
 * 三种输出形态统一由 loading 与 useCanvas 决定，卡片选择逻辑收敛在此。
 */
import type { LibrarySummary } from '@/types'
import ComicCard from '@/components/ComicCard.vue'
import HtmlCanvasCard from '@/components/HtmlCanvasCard.vue'
import { liveCacheKey, type LiveCacheState } from '@/stores/library'

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
}>()

defineEmits<{ favoriteToggled: [source: string, sourceId: string, favorite: boolean] }>()

const keyOf = (source: string, sourceId: string) => liveCacheKey(source, sourceId)
</script>

<template>
  <div v-if="loading" class="comic-grid" aria-label="加载中">
    <div v-for="index in 6" :key="index" class="skeleton-card">
      <div class="skeleton cover-skeleton" />
      <div class="skeleton line-skeleton" />
      <div class="skeleton line-skeleton short" />
    </div>
  </div>

  <div v-else-if="items.length" class="comic-grid">
    <template v-if="useCanvas">
      <HtmlCanvasCard
        v-for="item in items"
        :key="`canvas-${item.source}/${item.source_id}`"
        :comic="item"
        :enabled="true"
        :cache="liveCache?.[keyOf(item.source, item.source_id)]"
        @favorite-toggled="
          (source, sourceId, value) => $emit('favoriteToggled', source, sourceId, value)
        "
      />
    </template>
    <template v-else>
      <ComicCard
        v-for="item in items"
        :key="`dom-${item.source}/${item.source_id}`"
        :comic="item"
        :cache="liveCache?.[keyOf(item.source, item.source_id)]"
        :search-match="searchMatchMap?.get(`${item.source}_${item.source_id}`)"
        @favorite-toggled="
          (source, sourceId, value) => $emit('favoriteToggled', source, sourceId, value)
        "
      />
    </template>
  </div>

  <div v-else class="empty-shelf surface">
    <p class="empty-mark" aria-hidden="true">▤</p>
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
.comic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(15rem, 100%), 1fr));
  gap: var(--space-5);
  padding-top: var(--space-5);
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

.empty-mark {
  font-size: 3rem;
  color: var(--ink-2);
}
</style>

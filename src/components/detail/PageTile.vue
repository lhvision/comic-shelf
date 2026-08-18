<script setup lang="ts">
import { pageThumbUrl } from '@/api/client'

/**
 * 详情页页索引的单个 tile —— 缩略图 + 页码角标 + 缓存状态。
 * 使用 thumbnail（360px JPEG）而非原图，符合工程的性能约束。
 */
defineProps<{
  source: string
  sourceId: string
  index: number
  cached: boolean
}>()

function pageLabel(index: number) {
  return String(index).padStart(3, '0')
}
</script>

<template>
  <RouterLink
    :to="`/comic/${source}/${sourceId}/read/${index}`"
    class="page-tile"
    :data-cached="cached"
  >
    <div class="page-image">
      <img
        :src="pageThumbUrl(source, sourceId, index)"
        :alt="`第 ${index} 页`"
        loading="lazy"
        decoding="async"
      />
    </div>
    <span class="page-index">{{ pageLabel(index) }}</span>
    <span class="page-state">{{ cached ? '本地' : '待缓存' }}</span>
  </RouterLink>
</template>

<style scoped>
.page-tile {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-2);
  border: 1px solid var(--line);
  background: var(--paper-2);
  box-shadow: var(--shadow-1);
  content-visibility: auto;
  contain-intrinsic-size: auto 11rem;
  transition:
    translate var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out);
}

.page-tile:hover {
  translate: 0 -0.25rem;
  box-shadow: var(--shadow-2);
  border-color: var(--line-strong);
}

.page-image {
  aspect-ratio: 3 / 4.15;
  overflow: hidden;
  background: var(--paper-2);
}

.page-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top center;
}

.page-index {
  position: absolute;
  top: var(--space-2);
  left: var(--space-2);
  padding: var(--space-0-5) var(--space-2);
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--ink-0) 72%, transparent);
  color: var(--paper-0);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
}

.page-state {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  padding: var(--space-0-5) var(--space-2);
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--paper-0) 76%, transparent);
  color: var(--ink-1);
  font-size: var(--text-caption);
}

.page-tile[data-cached='true'] .page-state {
  color: var(--success);
}
</style>

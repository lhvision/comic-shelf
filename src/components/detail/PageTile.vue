<script setup lang="ts">
import { pageThumbUrl } from '@/api/client'

/**
 * 详情页页索引的单个 tile —— 缩略图 + 页码角标 + 缓存状态。
 * 使用 thumbnail（360px JPEG）而非原图，符合工程的性能约束。
 *
 * - `index` 是**全局页码**：缩略图 URL 与阅读器链接都走它；
 * - `label` 可选：子路由/章节视图传入本章本地页码，让 7000 页的长合集
 *   也显示「第 1–N 章内页」，而不是 2060 之类的全局大数字；
 * - `chapterId` 可选：从章节子路由进入阅读器时带上，返回键回子路由而不是父目录。
 */
const props = withDefaults(
  defineProps<{
    source: string
    sourceId: string
    index: number
    cached: boolean
    /** 展示用的页码（默认用全局 index） */
    label?: number
    /** 来源章节 id：阅读器返回时回到该章节子路由 */
    chapterId?: string
  }>(),
  { label: undefined, chapterId: '' },
)

function pageLabel(index: number) {
  return String(index).padStart(3, '0')
}

function displayNumber() {
  return props.label ?? props.index
}

function readerLink() {
  const base = `/comic/${props.source}/${props.sourceId}/read/${props.index}`
  return props.chapterId ? `${base}?chapter=${encodeURIComponent(props.chapterId)}` : base
}
</script>

<template>
  <RouterLink :to="readerLink()" class="page-tile" :data-cached="cached">
    <div class="page-image">
      <img
        :src="pageThumbUrl(source, sourceId, index)"
        :alt="`第 ${displayNumber()} 页`"
        loading="lazy"
        decoding="async"
      />
    </div>
    <span class="page-index">{{ pageLabel(displayNumber()) }}</span>
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
  font-size-adjust: ch-width 0.48;
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
  font-size-adjust: ic-width 0.6875;
}

.page-tile[data-cached='true'] .page-state {
  color: var(--success);
}
</style>

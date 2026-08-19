<script setup lang="ts">
import { ref, watch } from 'vue'
import { pageThumbUrl } from '@/api/client'
import type { Chapter } from '@/types'

/**
 * 章节目录里的单张章节卡片 —— 封面（该话第一页缩略图）+ 章节信息。
 * - 有图片就用第一页缩略图当封面；加载失败/无页面时回落到空白占位，仍显示章节信息。
 * - 点击进入该话的「章节子路由」（/comic/:source/:id/chapter/:chapterId）。
 * 纯展示组件，只依赖 props + 路由链接。
 */
const props = defineProps<{
  source: string
  sourceId: string
  chapter: Chapter
}>()

const coverFailed = ref(false)
const coverUrl = pageThumbUrl(props.source, props.sourceId, props.chapter.start)

watch(
  () => props.chapter.start,
  () => {
    coverFailed.value = false
  },
)

function onCoverError() {
  coverFailed.value = true
}
</script>

<template>
  <RouterLink :to="`/comic/${source}/${sourceId}/chapter/${chapter.id}`" class="chapter-card">
    <div class="chapter-cover" :data-blank="coverFailed || chapter.page_count === 0">
      <img
        v-if="chapter.page_count > 0"
        :src="coverUrl"
        :alt="`第 ${chapter.index} 話 封面`"
        loading="lazy"
        decoding="async"
        @error="onCoverError"
      />
    </div>
    <div class="chapter-info">
      <p class="eyebrow">第 {{ chapter.index }} 話</p>
      <h3 class="chapter-title">{{ chapter.title || `第 ${chapter.index} 話` }}</h3>
      <p class="chapter-meta">{{ chapter.page_count }} 页</p>
    </div>
  </RouterLink>
</template>

<style scoped>
.chapter-card {
  display: grid;
  grid-template-columns: minmax(4.6rem, 0.62fr) minmax(0, 1fr);
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  box-shadow: var(--shadow-1);
  transition:
    translate var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out);
}

.chapter-card:hover {
  translate: 0 -2px;
  border-color: var(--line-strong);
  box-shadow: var(--shadow-2);
}

.chapter-cover {
  position: relative;
  aspect-ratio: 3 / 4.15;
  border-radius: var(--radius-1);
  overflow: hidden;
  background:
    linear-gradient(135deg, var(--paper-1), var(--paper-2)),
    color-mix(in oklab, var(--paper-2) 70%, transparent);
}

.chapter-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top center;
}

/* 无图 / 加载失败时的空白占位：只留一条书脊色带，仍展示章节信息 */
.chapter-cover[data-blank='true']::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 3px;
  translate: -50% 0;
  background: color-mix(in oklab, var(--accent) 28%, transparent);
}

.chapter-info {
  min-width: 0;
  display: grid;
  gap: var(--space-1);
}

.chapter-title {
  font-size: var(--text-sm);
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.chapter-meta {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

@media (max-width: 480px) {
  .chapter-card {
    grid-template-columns: minmax(4.2rem, 0.7fr) minmax(0, 1fr);
  }
}
</style>

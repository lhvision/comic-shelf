<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { chapterCoverUrl } from '@/api/client'
import type { Chapter } from '@/types'

/**
 * 章节目录里的单张章节卡片 —— 封面（该话第一页）+ 章节信息 + 缓存进度。
 * - 封面走 T17「章节封面端点」（池化在 covers/chapters/）；加载失败/无页面时回落书脊占位。
 * - 点击进入该话的「章节子路由」（/comic/:source/:id/chapter/:chapterId）。
 * - 多章节本地缓存状态（T10）：父级传入 cachedPages，卡片显示「本地 N%」。
 * 纯展示组件，只依赖 props + 路由链接。
 */
const props = withDefaults(
  defineProps<{
    source: string
    sourceId: string
    chapter: Chapter
    /** 该话已本地缓存的页数（T10 章节级缓存进度） */
    cachedPages?: number
  }>(),
  { cachedPages: 0 },
)

const coverFailed = ref(false)
const coverUrl = chapterCoverUrl(props.source, props.sourceId, props.chapter.id)

watch(
  () => props.chapter.id,
  () => {
    coverFailed.value = false
  },
)

function onCoverError() {
  coverFailed.value = true
}

/** T10：本地缓存百分比文案；未缓存完单页或不传时隐藏。 */
const cachePercent = computed(() => {
  if (props.chapter.page_count <= 0) return null
  return Math.round((props.cachedPages / props.chapter.page_count) * 100)
})
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
      <p class="chapter-meta">
        {{ chapter.page_count }} 页
        <span v-if="cachePercent !== null && cachePercent > 0" class="chapter-cache"
          >· 本地 {{ cachePercent }}%</span
        >
      </p>
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

.chapter-cache {
  color: var(--success);
}

@media (max-width: 480px) {
  .chapter-card {
    grid-template-columns: minmax(4.2rem, 0.7fr) minmax(0, 1fr);
  }
}
</style>

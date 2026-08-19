<script setup lang="ts">
import ChapterCard from '@/components/detail/ChapterCard.vue'
import type { Chapter } from '@/types'

/**
 * 详情页「章节目录」整段 —— 多章节作品在详情页不铺开几千页，而是按章节
 * 摆成目录卡片；每张卡片（封面 + 章节信息）点击进入对应章节子路由。
 * 单章节作品不渲染本组件（由 ComicDetailView 直接渲染 PageIndexGrid）。
 */
defineProps<{
  source: string
  sourceId: string
  chapters: Chapter[]
  /** T10：每话已本地缓存的页数（chapterId -> cachedPages） */
  chapterCache?: Record<string, number>
}>()
</script>

<template>
  <section class="chapter-index" aria-labelledby="chapter-index-title">
    <div class="chapter-index-head">
      <div>
        <p class="eyebrow">Table of contents</p>
        <h2 id="chapter-index-title">章节目录</h2>
      </div>
      <p>共 {{ chapters.length }} 话 · 点击进入对应话的页面索引</p>
    </div>

    <div class="chapter-grid">
      <ChapterCard
        v-for="chapter in chapters"
        :key="chapter.id"
        :source="source"
        :source-id="sourceId"
        :chapter="chapter"
        :cached-pages="chapterCache?.[chapter.id] ?? 0"
      />
    </div>
  </section>
</template>

<style scoped>
.chapter-index {
  margin-top: var(--space-8);
}

.chapter-index-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--line);
}

.chapter-index-head h2 {
  margin-top: var(--space-1);
  font-size: var(--text-2xl);
}

.chapter-index-head > p {
  color: var(--ink-2);
  font-size: var(--text-sm);
}

.chapter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(20rem, 100%), 1fr));
  gap: var(--space-4);
  margin-top: var(--space-5);
}

@media (max-width: 640px) {
  .chapter-grid {
    grid-template-columns: 1fr;
  }

  .chapter-index-head {
    align-items: start;
    flex-direction: column;
    gap: var(--space-2);
  }
}
</style>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import ChapterCard from '@/components/detail/ChapterCard.vue'
import type { Chapter } from '@/types'

const CHAPTER_CHUNK_STEP = 24

/**
 * 详情页「章节目录」整段 —— 多章节作品在详情页不铺开几千页，而是按章节
 * 摆成目录卡片；每张卡片（封面 + 章节信息）点击进入对应章节子路由。
 *
 * 性能优化（ADR 0010）：面对 518074 等 152 话的长篇，采用分批增量渲染（默认首屏 24 话，
 * 结合底部哨兵自动追加），彻底根治瞬间渲染上百个卡片与并发网络图片导致的主线程假死与掉帧。
 */
const props = withDefaults(
  defineProps<{
    source: string
    sourceId: string
    chapters: Chapter[]
    /** 每话已本地缓存的页数（chapterId -> cachedPages） */
    chapterCache?: Record<string, number>
    /** 是否正在后台缓存中 */
    running?: boolean
    /** 当前正在缓存的 chapterId（若为整本缓存则为 null） */
    runningChapterId?: string | null
    /** 读者上次读到的章节序号（确保初始可见区间覆盖该章节） */
    initialVisibleChapter?: number
  }>(),
  {
    chapterCache: () => ({}),
    running: false,
    runningChapterId: null,
    initialVisibleChapter: 1,
  },
)

const expandedChapterCounts: Record<string, number> = {}

const emit = defineEmits<{
  (e: 'cacheChapter', chapterId: string): void
}>()

const comicKey = computed(() => `${props.source}/${props.sourceId}`)

const initialCount = computed(() => {
  const target = props.initialVisibleChapter || 1
  const remembered = expandedChapterCounts[comicKey.value] || 0
  const needed = Math.max(target, remembered)
  return Math.max(CHAPTER_CHUNK_STEP, Math.ceil(needed / CHAPTER_CHUNK_STEP) * CHAPTER_CHUNK_STEP)
})

const visibleCount = ref(initialCount.value)

watch(
  () => [props.chapters.length, comicKey.value],
  () => {
    visibleCount.value = initialCount.value
  },
)

const visibleChapters = computed(() => props.chapters.slice(0, visibleCount.value))
const remainingCount = computed(() => Math.max(0, props.chapters.length - visibleCount.value))

function loadMore() {
  visibleCount.value = Math.min(props.chapters.length, visibleCount.value + CHAPTER_CHUNK_STEP)
  expandedChapterCounts[comicKey.value] = visibleCount.value
}

function loadAll() {
  visibleCount.value = props.chapters.length
  expandedChapterCounts[comicKey.value] = visibleCount.value
}

const sentinelEl = ref<HTMLElement | null>(null)
useIntersectionObserver(
  sentinelEl,
  (entries) => {
    if (entries[0]?.isIntersecting && remainingCount.value > 0) {
      loadMore()
    }
  },
  { rootMargin: '600px 0px' },
)
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
        v-for="chapter in visibleChapters"
        :key="chapter.id"
        :source="source"
        :source-id="sourceId"
        :chapter="chapter"
        :cached-pages="chapterCache?.[chapter.id] ?? 0"
        :running="running && (!runningChapterId || runningChapterId === chapter.id)"
        @cache="emit('cacheChapter', $event)"
      />
    </div>

    <div v-if="remainingCount > 0" class="chapter-load-more-section">
      <div ref="sentinelEl" class="chapter-sentinel" aria-hidden="true" />
      <div class="chapter-more-actions">
        <button class="btn btn-secondary btn-sm" type="button" @click="loadMore">
          加载更多章节 (已显示 {{ visibleChapters.length }} / {{ chapters.length }} 话)
        </button>
        <button class="btn btn-ghost btn-sm" type="button" @click="loadAll">展开全部</button>
      </div>
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

.chapter-load-more-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: var(--space-6);
  gap: var(--space-3);
}

.chapter-sentinel {
  width: 100%;
  height: 1px;
  pointer-events: none;
}

.chapter-more-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
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

  .chapter-more-actions {
    flex-direction: column;
    width: 100%;
  }

  .chapter-more-actions .btn {
    width: 100%;
  }
}
</style>

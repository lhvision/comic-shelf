<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import ChapterCard from '@/components/detail/ChapterCard.vue'
import AppIcon from '@/components/AppIcon.vue'
import {
  getExpandedChapterCount,
  setExpandedChapterCount,
} from '@/composables/useChapterNavigation'
import type { Chapter } from '@/types'

const CHAPTER_CHUNK_STEP = 24

/**
 * 详情页「章节目录」整段 —— 多章节作品在详情页不铺开几千页，而是按章节
 * 摆成目录卡片；每张卡片（封面 + 章节信息）点击进入对应章节子路由。
 *
 * 性能优化（ADR 0010）：面对 518074 等 152 话的长篇，采用分批增量折叠渲染（默认首屏 24 话），
 * 彻底废除基于长距离 useIntersectionObserver 的贪婪无限滚动，提供可控的手动步进、全量展开与一键收起。
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

const emit = defineEmits<{
  cacheChapter: [chapterId: string]
}>()

const comicKey = computed(() => `${props.source}/${props.sourceId}`)
const indexWrapEl = ref<HTMLElement | null>(null)

const baseStepCount = computed(() => {
  const target = props.initialVisibleChapter || 1
  return Math.max(CHAPTER_CHUNK_STEP, Math.ceil(target / CHAPTER_CHUNK_STEP) * CHAPTER_CHUNK_STEP)
})

const initialCount = computed(() => {
  const remembered = getExpandedChapterCount(comicKey.value) || 0
  const needed = Math.max(baseStepCount.value, remembered)
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
const canCollapse = computed(() => visibleCount.value > baseStepCount.value)

function loadMore() {
  visibleCount.value = Math.min(props.chapters.length, visibleCount.value + CHAPTER_CHUNK_STEP)
  setExpandedChapterCount(comicKey.value, visibleCount.value)
}

function loadAll() {
  visibleCount.value = props.chapters.length
  setExpandedChapterCount(comicKey.value, visibleCount.value)
}

function collapse() {
  visibleCount.value = baseStepCount.value
  setExpandedChapterCount(comicKey.value, baseStepCount.value)
  void nextTick(() => {
    if (indexWrapEl.value && typeof indexWrapEl.value.scrollIntoView === 'function') {
      indexWrapEl.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}
</script>

<template>
  <section ref="indexWrapEl" class="chapter-index" aria-labelledby="chapter-index-title">
    <div class="chapter-index-head">
      <div>
        <p class="eyebrow">Table of contents</p>
        <h2 id="chapter-index-title">章节目录</h2>
      </div>
      <p>共 {{ chapters.length }} 话 · 点击进入对应话的页面索引</p>
    </div>

    <TransitionGroup tag="div" name="chapter-card" class="chapter-grid">
      <ChapterCard
        v-for="chapter in visibleChapters"
        :key="chapter.id"
        :source="source"
        :source-id="sourceId"
        :chapter="chapter"
        :cached-pages="chapterCache?.[chapter.id] ?? 0"
        :running="running && (!runningChapterId || runningChapterId === chapter.id)"
        :busy="running"
        @cache="emit('cacheChapter', $event)"
      />
    </TransitionGroup>

    <!-- 底部章节展开/收整控制条 -->
    <div v-if="remainingCount > 0 || canCollapse" class="chapter-load-more-section surface">
      <div class="chapter-sentinel-info">
        <AppIcon name="archive" size="sm" class="chapter-sentinel-icon" />
        <span class="chapter-sentinel-note">
          已展现 {{ visibleChapters.length }} / {{ chapters.length }} 话
          <template v-if="remainingCount > 0">（余 {{ remainingCount }} 话已折叠）</template>
          <template v-else>（全目录已展开）</template>
        </span>
      </div>

      <div class="chapter-more-actions">
        <button
          v-if="remainingCount > 0"
          class="btn btn-primary btn-sm"
          type="button"
          @click="loadMore"
        >
          <AppIcon name="chevron-down" size="xs" />
          再展开 {{ Math.min(CHAPTER_CHUNK_STEP, remainingCount) }} 话
        </button>
        <button
          v-if="remainingCount > 0"
          class="btn btn-ghost btn-sm"
          type="button"
          @click="loadAll"
        >
          <AppIcon name="book-open" size="xs" />
          展开全部
        </button>
        <button v-if="canCollapse" class="btn btn-ghost btn-sm" type="button" @click="collapse">
          <AppIcon name="chevron-up" size="xs" />
          收起目录
        </button>
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
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding: var(--space-3) var(--space-5);
  border-radius: var(--radius-2);
  border: 1px dashed var(--line);
  background: color-mix(in oklab, var(--paper-0) 88%, var(--paper-1));
}

.chapter-sentinel-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--ink-2);
  font-size: var(--text-sm);
}

.chapter-sentinel-icon {
  color: var(--accent);
  flex-shrink: 0;
}

.chapter-sentinel-note {
  letter-spacing: 0.01em;
}

.chapter-more-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
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

  .chapter-load-more-section {
    flex-direction: column;
    align-items: stretch;
    text-align: center;
  }

  .chapter-sentinel-info {
    justify-content: center;
  }

  .chapter-more-actions {
    flex-direction: column;
    width: 100%;
  }

  .chapter-more-actions .btn {
    width: 100%;
    min-height: 44px;
    justify-content: center;
  }
}

/* 章节卡片微动与进场动画 */
.chapter-card-enter-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-spring);
}

.chapter-card-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}

.chapter-card-move {
  transition: transform var(--duration-2) var(--ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .chapter-card-enter-active,
  .chapter-card-move {
    transition: none !important;
  }
}
</style>

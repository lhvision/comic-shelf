<script setup lang="ts">
/**
 * @file ReaderChapterBanners.vue
 * @description 阅读器跨话悬浮横幅组件（话首「← 上一话」与话末「本话完 · 下一话 →」）。
 *
 * 核心职责：
 * 1. 处于当前话首（`atChapterStart`）且存在上一话时渲染「← 上一话」按钮；
 * 2. 处于当前话末（`atChapterEnd`）且存在下一话时渲染「本话完 · 下一话 →」按钮；
 * 3. 纵向连续条漫模式下接入 CSS Scroll-Driven 滚动驱动浮入动画；
 * 4. 抛出跨话切页跳转事件（`prevChapter` / `nextChapter`）。
 */

import type { Chapter } from '@/types'
import type { ReaderSettings } from '@/composables/useReaderSettings'

/**
 * `ReaderChapterBanners` 组件 Props 契约
 */
export interface ReaderChapterBannersProps {
  /** 上一话元数据（无则为 null） */
  prevChapter: Chapter | null
  /** 下一话元数据（无则为 null） */
  nextChapter: Chapter | null
  /** 是否位于当前话第一页/第一屏 */
  atChapterStart: boolean
  /** 是否位于当前话末页/最后一屏 */
  atChapterEnd: boolean
  /** 章节简写标题格式化函数 */
  chapterShortLabel: (chapter: Chapter) => string
  /** 当前阅读器排版模式（用于激活纵向连续模式下的滚动驱动动效） */
  mode: ReaderSettings['mode']
}

defineProps<ReaderChapterBannersProps>()

defineEmits<{
  /** 点击上一话横幅事件 */
  prevChapter: []
  /** 点击下一话横幅事件 */
  nextChapter: []
}>()
</script>

<template>
  <button
    v-if="prevChapter && atChapterStart"
    class="reader-chapter-prev"
    type="button"
    @click="$emit('prevChapter')"
  >
    <span class="reader-chapter-prev-title">← 上一话：{{ chapterShortLabel(prevChapter) }}</span>
    <span>本话首</span>
  </button>

  <button
    v-if="nextChapter && atChapterEnd"
    class="reader-chapter-next"
    :data-mode="mode"
    type="button"
    @click="$emit('nextChapter')"
  >
    <span>本话完</span>
    <span class="reader-chapter-next-title">下一话：{{ chapterShortLabel(nextChapter) }} →</span>
  </button>
</template>

<style scoped>
/* T08：跨话翻页横幅 —— 呆在话首的「← 上一话」、话末的「本话完 · 下一话 →」 */
.reader-chapter-next,
.reader-chapter-prev {
  position: absolute;
  left: 50%;
  bottom: max(calc(var(--space-6) * 1), env(safe-area-inset-bottom));
  translate: -50% 0;
  z-index: 7;
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-height: var(--control-md);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--accent);
  border-radius: 999px;
  background: var(--reader-scrim-strong);
  color: var(--reader-ink);
  transition:
    background var(--duration-2) var(--ease-out),
    color var(--duration-2) var(--ease-out);
}

.reader-chapter-next:hover,
.reader-chapter-prev:hover {
  background: var(--accent);
  color: var(--paper-0);
}

.reader-chapter-next-title,
.reader-chapter-prev-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60vw;
}

@media (max-width: 680px) {
  .reader-chapter-next,
  .reader-chapter-prev {
    bottom: calc(
      var(--control-md) + max(var(--space-4), env(safe-area-inset-bottom)) + var(--space-2)
    );
  }
}

@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    /* 话末到达横幅浮入微动效 */
    .reader-chapter-next[data-mode='vertical-continuous'] {
      animation: reader-banner-appear 1ms var(--ease-out) both;
      animation-timeline: --reader-scroll;
      animation-range: calc(100% - 180px) 100%;
    }

    @keyframes reader-banner-appear {
      from {
        opacity: 0;
        transform: translate(-50%, 8px);
      }
      to {
        opacity: 1;
        transform: translate(-50%, 0);
      }
    }
  }
}
</style>

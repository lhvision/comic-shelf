<script setup lang="ts">
/**
 * @file ReaderChapterBanners.vue
 * @description 阅读器跨话悬浮横幅组件（话首「上一话」与话末「本话完 · 下一话」）。
 *
 * 核心职责：
 * 1. 处于当前话首（`atChapterStart`）且存在上一话时渲染「上一话」按钮；
 * 2. 处于当前话末（`atChapterEnd`）且存在下一话时渲染「本话完 · 下一话」按钮；
 * 3. 纵向连续条漫模式下接入 CSS Scroll-Driven 滚动驱动浮入动画；
 * 4. 严格收敛单行文本与文字溢出省略（ellipsis），防止移动端长标题折行撑开胶囊；
 * 5. 统一物理定位（`left: 50%; translate: -50% 0;`），杜绝 transform 叠加导致的偏位。
 */

import IconArrowLeft from '@/components/icons/IconArrowLeft.vue'
import IconArrowRight from '@/components/icons/IconArrowRight.vue'
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
    class="reader-chapter-banner reader-chapter-prev"
    type="button"
    @click="$emit('prevChapter')"
  >
    <IconArrowLeft :size="14" class="reader-chapter-icon" />
    <span class="reader-chapter-title">上一话：{{ chapterShortLabel(prevChapter) }}</span>
    <span class="reader-chapter-badge">本话首</span>
  </button>

  <button
    v-if="nextChapter && atChapterEnd"
    class="reader-chapter-banner reader-chapter-next"
    :data-mode="mode"
    type="button"
    @click="$emit('nextChapter')"
  >
    <span class="reader-chapter-badge">本话完</span>
    <span class="reader-chapter-title">下一话：{{ chapterShortLabel(nextChapter) }}</span>
    <IconArrowRight :size="14" class="reader-chapter-icon" />
  </button>
</template>

<style scoped>
/* T08：跨话翻页横幅 —— 呆在话首的「上一话」、话末的「本话完 · 下一话」 */
.reader-chapter-banner {
  position: absolute;
  left: 50%;
  bottom: max(var(--space-6), env(safe-area-inset-bottom, 0px));
  translate: -50% 0;
  z-index: 7;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  height: var(--control-md);
  max-height: var(--control-md);
  max-width: min(calc(100vw - var(--space-6) * 2), 26rem);
  padding: 0 var(--space-3);
  border: 1px solid var(--accent);
  border-radius: 999px;
  background: var(--reader-scrim-strong);
  color: var(--reader-ink);
  white-space: nowrap;
  box-sizing: border-box;
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  cursor: pointer;
  user-select: none;
  transition:
    background var(--duration-2) var(--ease-out),
    color var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out);
}

.reader-chapter-banner:hover {
  background: var(--accent);
  color: var(--paper-0);
}

.reader-chapter-icon {
  flex-shrink: 0;
}

.reader-chapter-badge {
  flex-shrink: 0;
  white-space: nowrap;
  font-size: var(--text-xs);
  font-family: var(--font-sans);
  opacity: 0.85;
}

.reader-chapter-title {
  flex: 0 1 auto;
  min-width: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: clamp(5rem, 36vw, 14rem);
}

@media (max-width: 680px) {
  .reader-chapter-banner {
    bottom: calc(
      var(--control-md) + max(var(--space-4), env(safe-area-inset-bottom, 0px)) + var(--space-2)
    );
    max-width: calc(100vw - var(--space-4) * 2);
    padding: 0 var(--space-2-5, 0.625rem);
    gap: var(--space-1-5, 0.375rem);
  }

  .reader-chapter-title {
    max-width: clamp(4rem, 42vw, 11rem);
  }
}

@supports (animation-timeline: scroll()) {
  @media (prefers-reduced-motion: no-preference) {
    /* 话末到达横幅浮入微动效：直接使用 translate 属性，与基类 translate: -50% 0 协调，避免 transform 叠加 */
    .reader-chapter-next[data-mode='vertical-continuous'] {
      animation: reader-banner-appear 1ms var(--ease-out) both;
      animation-timeline: --reader-scroll;
      animation-range: calc(100% - 180px) 100%;
    }

    @keyframes reader-banner-appear {
      from {
        opacity: 0;
        translate: -50% 8px;
      }
      to {
        opacity: 1;
        translate: -50% 0;
      }
    }
  }
}
</style>

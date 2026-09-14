<script setup lang="ts">
/**
 * @file ReaderBubbleOverlay.vue
 * @description 阅读器台词对白气泡呼吸高亮覆盖层（Breathing Bubble Overlay）。
 *
 * 核心契约：
 * 1. 监听当前画页 `pageIndex`、目标气泡 `targetBubble` 与底图就绪状态 `imageReady`；
 * 2. 纯 CSS 原生百分比自适应排版：
 *    - `top: box[0] * 100%`
 *    - `left: box[1] * 100%`
 *    - `height: (box[2] - box[0]) * 100%`
 *    - `width: (box[3] - box[1]) * 100%`
 * 3. 视觉质感：
 *    - 温润朱砂金墨色线框与琥珀朱砂微底（oklch(0.59 0.17 38) 与暖金调和，绝无紫蓝渐变与廉价毛玻璃）；
 *    - 优雅 2 秒呼吸脉冲动效（@keyframes breathing-pulse），随后自然淡出；
 * 4. 无障碍与交互安全：
 *    - 全程声明 `pointer-events: none`，零阻碍点击、翻页与画卷滚动；
 *    - 适配屏幕阅读器可访问性（role="status", aria-live="polite"）；
 *    - 严守 `prefers-reduced-motion` 动效降级规范；
 *    - 视口防碰撞：顶部分镜自动翻转至下方，右侧分镜自适应靠右对齐。
 */

import { computed } from 'vue'
import type { TargetBubble } from '@/composables/useReaderBubble'

export type { TargetBubble }

export interface ReaderBubbleOverlayProps {
  /** 当前画卷渲染的全局页码 */
  pageIndex: number
  /** 待高亮的目标气泡 */
  targetBubble?: TargetBubble | null
  /** 底图加载就绪指示（加载期阻断动效提前夭折） */
  imageReady?: boolean
}

const props = withDefaults(defineProps<ReaderBubbleOverlayProps>(), {
  targetBubble: null,
  imageReady: true,
})

const isMatched = computed(() => {
  if (!props.imageReady) return false
  if (!props.targetBubble) return false
  if (props.targetBubble.page !== props.pageIndex) return false
  const { box } = props.targetBubble
  return (
    Array.isArray(box) &&
    box.length === 4 &&
    box.every((n) => typeof n === 'number' && Number.isFinite(n))
  )
})

function formatPercent(val: number): number {
  return Math.round(val * 10000) / 10000
}

const boxStyle = computed(() => {
  if (!isMatched.value || !props.targetBubble) return {}
  const [ymin, xmin, ymax, xmax] = props.targetBubble.box

  const top = formatPercent(Math.max(0, Math.min(100, ymin * 100)))
  const left = formatPercent(Math.max(0, Math.min(100, xmin * 100)))
  const height = formatPercent(Math.max(0, Math.min(100 - top, (ymax - ymin) * 100)))
  const width = formatPercent(Math.max(0, Math.min(100 - left, (xmax - xmin) * 100)))

  return {
    top: `${top}%`,
    left: `${left}%`,
    height: `${height}%`,
    width: `${width}%`,
  }
})

const bubbleText = computed(() => props.targetBubble?.text?.trim() || '')

const calloutClasses = computed(() => {
  if (!props.targetBubble) return []
  const [ymin, xmin] = props.targetBubble.box
  const classes: string[] = []
  if (ymin < 0.12) {
    classes.push('is-placement-bottom')
  }
  if (xmin > 0.65) {
    classes.push('is-align-right')
  }
  return classes
})
</script>

<template>
  <div
    v-if="isMatched"
    class="reader-bubble-overlay"
    role="status"
    aria-live="polite"
    :aria-label="bubbleText ? `命中对白：${bubbleText}` : '台词气泡高亮位置'"
  >
    <div class="reader-bubble-box" :style="boxStyle">
      <div v-if="bubbleText" class="bubble-callout" :class="calloutClasses">
        <span class="bubble-callout-text">{{ bubbleText }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reader-bubble-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 10;
  overflow: visible;
}

.reader-bubble-box {
  position: absolute;
  box-sizing: border-box;
  pointer-events: none;
  border-radius: var(--radius-1);
  /* 温润朱砂金墨色边框：以品牌朱砂主色融合暖金纸色 */
  border: 2px solid color-mix(in oklab, var(--accent) 84%, var(--warning) 16%);
  /* 宣纸暖琥珀朱砂光晕背景 */
  background: color-mix(
    in oklab,
    var(--accent) 12%,
    color-mix(in oklab, var(--warning) 8%, transparent)
  );
  /* 细致朱砂呼吸光晕与微投影 */
  box-shadow:
    0 0 0 1px color-mix(in oklab, var(--accent) 50%, transparent),
    0 0 18px color-mix(in oklab, var(--accent) 35%, transparent),
    inset 0 0 12px color-mix(in oklab, var(--accent) 15%, transparent);
  animation: breathing-pulse 2.2s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  will-change: transform, opacity;
}

/* 命中台词微标胶囊 */
.bubble-callout {
  position: absolute;
  bottom: calc(100% + var(--space-1));
  left: 0;
  max-width: min(20rem, 80vw);
  padding: var(--space-badge-y) var(--space-badge-x);
  background: color-mix(in oklab, var(--reader-bg) 92%, var(--accent) 8%);
  border: 1px solid color-mix(in oklab, var(--accent) 55%, transparent);
  border-radius: var(--radius-1);
  box-shadow: var(--shadow-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bubble-callout.is-placement-bottom {
  bottom: auto;
  top: calc(100% + var(--space-1));
}

.bubble-callout.is-align-right {
  left: auto;
  right: 0;
}

.bubble-callout-text {
  font-family: var(--font-body);
  font-size: var(--text-caption);
  color: var(--reader-ink);
  letter-spacing: 0.02em;
}

/* 2秒自然律动呼吸脉冲与平滑淡出 */
@keyframes breathing-pulse {
  0% {
    opacity: 0;
    transform: scale(0.96);
    box-shadow:
      0 0 0 1px color-mix(in oklab, var(--accent) 30%, transparent),
      0 0 8px color-mix(in oklab, var(--accent) 20%, transparent);
  }
  16% {
    opacity: 1;
    transform: scale(1);
    box-shadow:
      0 0 0 2px color-mix(in oklab, var(--accent) 80%, transparent),
      0 0 22px color-mix(in oklab, var(--accent) 50%, transparent),
      inset 0 0 14px color-mix(in oklab, var(--accent) 20%, transparent);
  }
  42% {
    opacity: 0.95;
    transform: scale(1.015);
    box-shadow:
      0 0 0 2.5px color-mix(in oklab, var(--accent) 95%, var(--warning) 5%),
      0 0 26px color-mix(in oklab, var(--accent) 60%, transparent),
      inset 0 0 18px color-mix(in oklab, var(--accent) 25%, transparent);
  }
  68% {
    opacity: 0.9;
    transform: scale(1);
    box-shadow:
      0 0 0 1.5px color-mix(in oklab, var(--accent) 70%, transparent),
      0 0 16px color-mix(in oklab, var(--accent) 35%, transparent),
      inset 0 0 10px color-mix(in oklab, var(--accent) 15%, transparent);
  }
  84% {
    opacity: 0.55;
    transform: scale(0.99);
    box-shadow:
      0 0 0 1px color-mix(in oklab, var(--accent) 40%, transparent),
      0 0 10px color-mix(in oklab, var(--accent) 20%, transparent);
  }
  100% {
    opacity: 0;
    transform: scale(0.98);
    box-shadow: none;
    visibility: hidden;
  }
}

/* 动效无障碍降级 */
@media (prefers-reduced-motion: reduce) {
  .reader-bubble-box {
    animation: breathing-static 2s linear forwards;
    transform: none !important;
  }

  @keyframes breathing-static {
    0% {
      opacity: 0;
    }
    10% {
      opacity: 0.95;
    }
    80% {
      opacity: 0.95;
    }
    100% {
      opacity: 0;
      visibility: hidden;
    }
  }
}
</style>

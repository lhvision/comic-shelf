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
 *    - `targetBubble.others`（同页其余命中气泡）只画 1px 静态细描边，走 `ghost-mark` 同一条
 *      2.2s 时间轴与代表格同时淡出，不带 callout、不带光晕，避免与检索主体抢视觉焦点；
 * 4. 无障碍与交互安全：
 *    - 全程声明 `pointer-events: none`，零阻碍点击、翻页与画卷滚动；
 *    - 适配屏幕阅读器可访问性（role="status", aria-live="polite"）；
 *    - 严守 `prefers-reduced-motion` 动效降级规范；
 *    - 视口防碰撞：顶部分镜自动翻转至下方，右侧分镜自适应靠右对齐。
 */

import { computed } from 'vue'
import { clamp, round } from '@/utils/math'
import type { BubbleBox, TargetBubble } from '@/composables/useReaderBubble'

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

function boxToPercentStyle(box: BubbleBox) {
  const [ymin, xmin, ymax, xmax] = box

  const top = round(clamp(ymin * 100, 0, 100), 4)
  const left = round(clamp(xmin * 100, 0, 100), 4)
  const height = round(clamp((ymax - ymin) * 100, 0, 100 - top), 4)
  const width = round(clamp((xmax - xmin) * 100, 0, 100 - left), 4)

  return {
    top: `${top}%`,
    left: `${left}%`,
    height: `${height}%`,
    width: `${width}%`,
  }
}

const boxStyle = computed(() => {
  if (!isMatched.value || !props.targetBubble) return {}
  return boxToPercentStyle(props.targetBubble.box)
})

/** 同页其余命中格：只作静态描边，不参与定位与 callout */
const otherBoxes = computed<BubbleBox[]>(() =>
  isMatched.value ? (props.targetBubble?.others ?? []) : [],
)

const otherStyles = computed(() => otherBoxes.value.map((b) => boxToPercentStyle(b)))

const ariaLabel = computed(() => {
  // 只报"画了几格"，不报"命中几处"：覆盖层拿不到后端的 bubble_count，
  // 且描边框封顶 6 格，用"命中"措辞会在高频页谎报总数
  const extra = otherBoxes.value.length
  const scope = extra > 0 ? `（同页一并描出 ${extra} 处气泡）` : ''
  return bubbleText.value ? `命中对白：${bubbleText.value}${scope}` : `台词气泡高亮位置${scope}`
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
    :aria-label="ariaLabel"
  >
    <div class="reader-bubble-box" :style="boxStyle">
      <div v-if="bubbleText" class="bubble-callout" :class="calloutClasses">
        <span class="bubble-callout-text">{{ bubbleText }}</span>
      </div>
    </div>
    <div v-if="otherStyles.length > 0" class="reader-bubble-others" aria-hidden="true">
      <div v-for="(style, i) in otherStyles" :key="i" class="reader-bubble-ghost" :style="style" />
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

/* 同页其余命中格：静态细描边、无底纹无光晕，不与代表格的呼吸抢焦点 */
.reader-bubble-others {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.reader-bubble-ghost {
  position: absolute;
  box-sizing: border-box;
  pointer-events: none;
  border-radius: var(--radius-1);
  border: 1px solid color-mix(in oklab, var(--accent) 70%, transparent);
  /* 内外各一道对比键线：描边压在任意漫画底图上（深色场、密网点、纯白气泡都可能遇到），
     只靠半透明朱砂在暗场几乎不可见。这两道刻意不随主题翻转——它们要对的是图片，不是纸面 */
  box-shadow:
    0 0 0 1px rgb(0 0 0 / 55%),
    inset 0 0 0 1px rgb(255 255 255 / 40%);
  animation: ghost-mark 2.2s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  will-change: opacity;
}

/* 与代表格同一条 2.2s 时间轴：同时出现、同时淡出 */
@keyframes ghost-mark {
  0% {
    opacity: 0;
  }
  16% {
    opacity: 1;
  }
  84% {
    opacity: 0.5;
  }
  100% {
    opacity: 0;
    visibility: hidden;
  }
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

  .reader-bubble-ghost {
    animation: breathing-static 2s linear forwards;
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

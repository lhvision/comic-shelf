<script setup lang="ts">
import { computed } from 'vue'
import { useId } from 'vue'

/**
 * 基于 CSS Anchor Positioning 的轻量 Tooltip。
 * - 触发元素上设 `anchor-name`，浮层设 `position-anchor` + `position-area`
 * - hover / focus-within 显示，fade + 微位移，全部走 tokens
 * - 支持 top / right / bottom / left（默认 top）
 * - 不支持锚点定位的浏览器优雅降级为绝对定位（相对包裹层下方居中）
 */
const props = withDefaults(
  defineProps<{
    tip: string
    /** top / right / bottom / left（默认 top） */
    side?: 'top' | 'right' | 'bottom' | 'left'
    /** start / center / end（相对触发元素的起始/居中/末尾） */
    align?: 'start' | 'center' | 'end'
    /** 浮层宽度 */
    width?: string
  }>(),
  { side: 'top', align: 'center', width: '15rem' },
)

const uid = useId().replace(/[^a-zA-Z0-9_-]+/g, '')
const anchorName = `--tip-${uid}`
const tipId = `tip-${uid}`

const areaMap: Record<string, string> = {
  'top start': 'top left',
  'top center': 'top center',
  'top end': 'top right',
  'right start': 'right top',
  'right center': 'right center',
  'right end': 'right bottom',
  'bottom start': 'bottom left',
  'bottom center': 'bottom center',
  'bottom end': 'bottom right',
  'left start': 'left top',
  'left center': 'left center',
  'left end': 'left bottom',
}

const positionArea = computed(() => areaMap[`${props.side} ${props.align}`] ?? 'top center')
const anchorStyle = computed(() => ({ 'anchor-name': anchorName }))
const tipStyle = computed(() => ({
  'position-anchor': anchorName,
  'position-area': positionArea.value,
  '--tip-width': props.width,
}))
</script>

<template>
  <span class="tooltip">
    <span
      class="tooltip__trigger"
      :style="anchorStyle"
      :aria-describedby="tipId"
      :data-tip-id="tipId"
    >
      <slot />
    </span>

    <span :id="tipId" role="tooltip" class="tooltip__tip" :style="tipStyle" :data-side="side">
      {{ tip }}
    </span>
  </span>
</template>

<style scoped>
.tooltip {
  display: inline-flex;
  position: relative;
}

.tooltip__trigger {
  display: inline-flex;
  align-items: center;
  cursor: help;
}

.tooltip__tip {
  position: fixed;
  width: var(--tip-width);
  max-width: min(calc(100vw - 2rem), var(--tip-width));
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-1);
  box-shadow: var(--shadow-2);
  font-size: var(--text-xs);
  line-height: 1.6;
  text-align: left;
  opacity: 0;
  visibility: hidden;
  z-index: 40;
  pointer-events: none;
  translate: 0 4px;
  transition:
    opacity var(--duration-1) var(--ease-out),
    translate var(--duration-1) var(--ease-out),
    visibility var(--duration-1) step-end;
  position-try-fallback: flip-block;
  position-visibility: anchors-visible;
}

.tooltip__tip[data-side='top'] {
  translate: 0 -4px;
}
.tooltip__tip[data-side='left'] {
  translate: -4px 0;
}
.tooltip__tip[data-side='right'] {
  translate: 4px 0;
}

.tooltip:hover .tooltip__tip,
.tooltip:focus-within .tooltip__tip {
  opacity: 1;
  visibility: visible;
  translate: 0 0;
  transition:
    opacity var(--duration-1) var(--ease-out),
    translate var(--duration-1) var(--ease-out),
    visibility var(--duration-1) step-start;
}

/* 锚点定位不可用时：绝对定位到触发元素下方居中 */
@supports not (anchor-name: --tooltip-fallback) {
  .tooltip__tip {
    position: absolute;
    top: calc(100% + var(--space-2));
    left: 50%;
    translate: -50% 4px;
  }

  .tooltip:hover .tooltip__tip,
  .tooltip:focus-within .tooltip__tip {
    translate: -50% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tooltip__tip {
    transition: none;
  }
}
</style>

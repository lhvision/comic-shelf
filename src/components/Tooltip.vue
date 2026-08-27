<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId } from 'vue'

/**
 * 现代轻量气泡提示组件（Modern AppTooltip）。
 * - 结合 HTML Popover API (popover="hint") 与 CSS Anchor Positioning
 * - 支持 @container anchored(fallback: flip-block) 容器回退检测自适应翻转
 * - 支持 top / right / bottom / left 与 start / center / end 对齐
 * - 支持 hover / focus-within 唤起与无障碍 aria-describedby
 * - 非现代浏览器优雅降级为绝对定位与 Vue 状态控制
 */
const props = withDefaults(
  defineProps<{
    tip?: string
    /** 浮动方位：top / right / bottom / left（默认 top） */
    side?: 'top' | 'right' | 'bottom' | 'left'
    /** 对齐方式：start / center / end（相对触发元素，默认 center） */
    align?: 'start' | 'center' | 'end'
    /** 浮层宽度 */
    width?: string
    /** 显式禁用 */
    disabled?: boolean
    /** 是否显示指示小三角 */
    arrow?: boolean
    /** 唤起延迟 (ms) */
    delay?: number
  }>(),
  {
    tip: '',
    side: 'top',
    align: 'center',
    width: '15rem',
    disabled: false,
    arrow: true,
    delay: 100,
  },
)

const uid = useId().replace(/[^a-zA-Z0-9_-]+/g, '')
const anchorName = computed(() => `--tip-${uid}`)
const tipId = `tip-${uid}`

const areaMap: Record<string, string> = {
  'top start': 'top span-right',
  'top center': 'top',
  'top end': 'top span-left',
  'bottom start': 'bottom span-right',
  'bottom center': 'bottom',
  'bottom end': 'bottom span-left',
  'left start': 'left span-bottom',
  'left center': 'left',
  'left end': 'left span-top',
  'right start': 'right span-bottom',
  'right center': 'right',
  'right end': 'right span-top',
}

const positionArea = computed(() => areaMap[`${props.side} ${props.align}`] ?? 'top')

const justifySelf = computed(() => {
  if (props.side === 'left' || props.side === 'right') return undefined
  if (props.align === 'start') return 'start'
  if (props.align === 'end') return 'end'
  return 'anchor-center'
})

const alignSelf = computed(() => {
  if (props.side === 'top' || props.side === 'bottom') return undefined
  if (props.align === 'start') return 'start'
  if (props.align === 'end') return 'end'
  return 'anchor-center'
})

const isVisible = ref(false)
const tipElement = ref<HTMLElement | null>(null)
let showTimer: ReturnType<typeof setTimeout> | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

function show() {
  if (props.disabled) return
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
  showTimer = setTimeout(() => {
    isVisible.value = true
    try {
      if (tipElement.value && typeof tipElement.value.showPopover === 'function') {
        if (!tipElement.value.matches(':popover-open')) {
          tipElement.value.showPopover()
        }
      }
    } catch {
      // 忽略不支持或已展开情况
    }
  }, props.delay)
}

function onTipEnter() {
  if (props.disabled) return
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function onTipLeave() {
  hide()
}

function hide() {
  if (showTimer) {
    clearTimeout(showTimer)
    showTimer = null
  }
  if (hideTimer) {
    clearTimeout(hideTimer)
  }
  hideTimer = setTimeout(() => {
    isVisible.value = false
    try {
      if (tipElement.value && typeof tipElement.value.hidePopover === 'function') {
        if (tipElement.value.matches(':popover-open')) {
          tipElement.value.hidePopover()
        }
      }
    } catch {
      // 忽略不支持或已收起情况
    }
  }, 150)
}

onBeforeUnmount(() => {
  if (showTimer) clearTimeout(showTimer)
  if (hideTimer) clearTimeout(hideTimer)
})
</script>

<template>
  <span
    class="tooltip-wrapper"
    @mouseenter="show"
    @mouseleave="hide"
    @focusin="show"
    @focusout="hide"
  >
    <span
      class="tooltip__trigger"
      :aria-describedby="disabled ? undefined : tipId"
      :data-tip-anchor="anchorName"
      :interestfor="disabled ? undefined : tipId"
    >
      <slot />
    </span>

    <span
      :id="tipId"
      ref="tipElement"
      popover="hint"
      role="tooltip"
      class="tooltip__tip"
      :class="{
        'is-visible': isVisible,
        'has-arrow': arrow,
        [`side-${side}`]: true,
        [`align-${align}`]: true,
      }"
      :data-side="side"
      @mouseenter="onTipEnter"
      @mouseleave="onTipLeave"
    >
      <slot name="content">
        {{ tip }}
      </slot>
    </span>
  </span>
</template>

<style scoped>
.tooltip-wrapper {
  display: inline-flex;
  position: relative;
  vertical-align: middle;
}

.tooltip__trigger {
  display: inline-flex;
  align-items: center;
  anchor-name: v-bind(anchorName);
}

.tooltip__tip {
  /* 原生 Popover 样式重置与防幽灵滚动条 */
  margin: 0;
  inset: auto;
  overflow: visible;
  box-sizing: border-box;
  border: 1px solid var(--line-strong);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-1);
  box-shadow: var(--shadow-2);
  font-size: var(--text-xs);
  font-family: var(--font-body);
  line-height: 1.6;
  text-align: left;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  pointer-events: auto;
  user-select: text;
  cursor: default;
  width: max-content;
  max-width: min(calc(100vw - 2rem), v-bind('props.width'));

  /* CSS Anchor 定位与顶层 */
  position: fixed;
  position-anchor: v-bind(anchorName);
  position-area: v-bind(positionArea);
  justify-self: v-bind(justifySelf);
  align-self: v-bind(alignSelf);
  position-try-fallbacks: flip-block, flip-inline;
  container-type: anchored;

  /* 进退场与离散动画 */
  opacity: 0;
  visibility: hidden;
  translate: 0 4px;
  transition:
    opacity var(--duration-1) var(--ease-out),
    translate var(--duration-1) var(--ease-out),
    visibility var(--duration-1) step-end,
    overlay var(--duration-1) var(--ease-out) allow-discrete,
    display var(--duration-1) var(--ease-out) allow-discrete;
}

/* 各方位默认位移动效 */
.tooltip__tip[data-side='top'] {
  translate: 0 -4px;
  margin-bottom: var(--space-1-5);
}
.tooltip__tip[data-side='bottom'] {
  translate: 0 4px;
  margin-top: var(--space-1-5);
}
.tooltip__tip[data-side='left'] {
  translate: -4px 0;
  margin-right: var(--space-1-5);
}
.tooltip__tip[data-side='right'] {
  translate: 4px 0;
  margin-left: var(--space-1-5);
}

/* 激活态（结合 JS is-visible、:popover-open 或原生 :interest-target） */
.tooltip__tip.is-visible,
.tooltip__tip:popover-open,
.tooltip-wrapper:hover .tooltip__tip,
.tooltip-wrapper:focus-within .tooltip__tip {
  opacity: 1;
  visibility: visible;
  translate: 0 0;
  transition:
    opacity var(--duration-1) var(--ease-out),
    translate var(--duration-1) var(--ease-out),
    visibility var(--duration-1) step-start;
}

/* 小三角指示器 */
.tooltip__tip.has-arrow::before {
  content: '';
  position: absolute;
  width: 0.5rem;
  height: 0.5rem;
  background: var(--paper-0);
  border: 1px solid var(--line-strong);
  transform: rotate(45deg);
  pointer-events: none;
}

/* 方位基准偏移（Side） */
.tooltip__tip.side-top::before {
  bottom: -0.3rem;
  border-top: none;
  border-left: none;
}

.tooltip__tip.side-bottom::before {
  top: -0.3rem;
  border-bottom: none;
  border-right: none;
}

.tooltip__tip.side-left::before {
  right: -0.3rem;
  border-bottom: none;
  border-left: none;
}

.tooltip__tip.side-right::before {
  left: -0.3rem;
  border-top: none;
  border-right: none;
}

/* 对齐基准偏移（Align）：保证指示小三角永远精准对齐触发源图标 */
.tooltip__tip.side-top.align-center::before,
.tooltip__tip.side-bottom.align-center::before {
  left: 50%;
  right: auto;
  translate: -50% 0;
}

.tooltip__tip.side-top.align-start::before,
.tooltip__tip.side-bottom.align-start::before {
  left: 0.85rem;
  right: auto;
  translate: 0 0;
}

.tooltip__tip.side-top.align-end::before,
.tooltip__tip.side-bottom.align-end::before {
  left: auto;
  right: 0.85rem;
  translate: 0 0;
}

.tooltip__tip.side-left.align-center::before,
.tooltip__tip.side-right.align-center::before {
  top: 50%;
  bottom: auto;
  translate: 0 -50%;
}

.tooltip__tip.side-left.align-start::before,
.tooltip__tip.side-right.align-start::before {
  top: 0.85rem;
  bottom: auto;
  translate: 0 0;
}

.tooltip__tip.side-left.align-end::before,
.tooltip__tip.side-right.align-end::before {
  top: auto;
  bottom: 0.85rem;
  translate: 0 0;
}

/* 悬停安全桥（Hover Bridge）：透明扩展触控区，连接触发元素与气泡，防止跨空隙时失焦 */
.tooltip__tip::after {
  content: '';
  position: absolute;
  pointer-events: auto;
}

.tooltip__tip[data-side='top']::after {
  left: 0;
  right: 0;
  bottom: calc(-1 * var(--space-2));
  height: var(--space-2);
}

.tooltip__tip[data-side='bottom']::after {
  left: 0;
  right: 0;
  top: calc(-1 * var(--space-2));
  height: var(--space-2);
}

.tooltip__tip[data-side='left']::after {
  top: 0;
  bottom: 0;
  right: calc(-1 * var(--space-2));
  width: var(--space-2);
}

.tooltip__tip[data-side='right']::after {
  top: 0;
  bottom: 0;
  left: calc(-1 * var(--space-2));
  width: var(--space-2);
}

/* 容器查询回退检测（Chrome 143+ 原生感知 flip-block 翻转） */
@container anchored(fallback: flip-block) {
  .tooltip__tip.side-top::before {
    bottom: auto;
    top: -0.3rem;
    border-top: 1px solid var(--line-strong);
    border-left: 1px solid var(--line-strong);
    border-bottom: none;
    border-right: none;
  }
  .tooltip__tip.side-bottom::before {
    top: auto;
    bottom: -0.3rem;
    border-bottom: 1px solid var(--line-strong);
    border-right: 1px solid var(--line-strong);
    border-top: none;
    border-left: none;
  }
  .tooltip__tip[data-side='top']::after {
    bottom: auto;
    top: calc(-1 * var(--space-2));
    height: var(--space-2);
  }
  .tooltip__tip[data-side='bottom']::after {
    top: auto;
    bottom: calc(-1 * var(--space-2));
    height: var(--space-2);
  }
}

/* 锚点定位不可用时的优雅降级（传统 absolute 定位） */
@supports not (anchor-name: --tooltip-anchor-test) {
  .tooltip__tip {
    position: absolute;
    z-index: 50;
  }

  .tooltip__tip.side-top {
    bottom: calc(100% + var(--space-1-5));
    left: 50%;
    translate: -50% -4px;
  }

  .tooltip__tip.side-bottom {
    top: calc(100% + var(--space-1-5));
    left: 50%;
    translate: -50% 4px;
  }

  .tooltip__tip.is-visible.side-top,
  .tooltip-wrapper:hover .tooltip__tip.side-top,
  .tooltip-wrapper:focus-within .tooltip__tip.side-top {
    translate: -50% 0;
  }

  .tooltip__tip.is-visible.side-bottom,
  .tooltip-wrapper:hover .tooltip__tip.side-bottom,
  .tooltip-wrapper:focus-within .tooltip__tip.side-bottom {
    translate: -50% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tooltip__tip {
    transition: none;
    translate: 0 0 !important;
  }
}
</style>

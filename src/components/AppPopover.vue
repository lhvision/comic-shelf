<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { onClickOutside } from '@vueuse/core'

/**
 * 现代通用弹出层组件（AppPopover）。
 * - 结合 HTML Popover API (popover="auto") 与 CSS Anchor Positioning
 * - 享受原生 Top Layer 顶层层级（免受父级 overflow 截断与 z-index 冲突）
 * - 原生支持失焦自动关闭（Light Dismiss / Esc）
 * - 兼容 click、hover 与 manual 触发模式，非现代浏览器提供稳健回退
 */
const props = withDefaults(
  defineProps<{
    open?: boolean
    /** 弹出方位：top / bottom / left / right（默认 bottom） */
    side?: 'top' | 'bottom' | 'left' | 'right'
    /** 对齐方式：start / center / end（默认 start） */
    align?: 'start' | 'center' | 'end'
    /** 触发方式：click / hover / manual（默认 click） */
    trigger?: 'click' | 'hover' | 'manual'
    /** 禁用状态 */
    disabled?: boolean
    /** 是否带指示箭头 */
    arrow?: boolean
    /** 宽度（可选，如 18rem） */
    width?: string
    /** 无障碍标签 */
    ariaLabel?: string
    /** 面板无障碍角色（默认由 ariaLabel 决定为 'region'） */
    role?: string
  }>(),
  {
    open: undefined,
    side: 'bottom',
    align: 'start',
    trigger: 'click',
    disabled: false,
    arrow: false,
    width: undefined,
    ariaLabel: '弹出面板',
    role: undefined,
  },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  open: []
  close: []
}>()

const uid = useId().replace(/[^a-zA-Z0-9_-]+/g, '')
const anchorName = computed(() => `--popover-${uid}`)
const popoverId = `popover-${uid}`

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

const positionArea = computed(() => areaMap[`${props.side} ${props.align}`] ?? 'bottom span-right')

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

const internalOpen = ref(props.open ?? false)
const isOpen = computed(() => (props.open !== undefined ? props.open : internalOpen.value))

const popoverEl = ref<HTMLElement | null>(null)
const triggerEl = ref<HTMLElement | null>(null)
const rootEl = ref<HTMLElement | null>(null)

let hoverTimer: ReturnType<typeof setTimeout> | null = null

function openPopover() {
  if (props.disabled || isOpen.value) return
  if (props.open === undefined) internalOpen.value = true
  emit('update:open', true)
  emit('open')

  nextTick(() => {
    try {
      if (popoverEl.value && typeof popoverEl.value.showPopover === 'function') {
        if (!popoverEl.value.matches(':popover-open')) {
          popoverEl.value.showPopover()
        }
      }
    } catch {
      // 忽略不支持
    }
  })
}

function closePopover() {
  if (!isOpen.value) return
  if (props.open === undefined) internalOpen.value = false
  emit('update:open', false)
  emit('close')

  try {
    if (popoverEl.value && typeof popoverEl.value.hidePopover === 'function') {
      if (popoverEl.value.matches(':popover-open')) {
        popoverEl.value.hidePopover()
      }
    }
  } catch {
    // 忽略不支持
  }
}

function toggle() {
  if (props.disabled) return
  if (isOpen.value) {
    closePopover()
  } else {
    openPopover()
  }
}

// 监听 popover 原生 toggle 事件（如用户点外部或按 Esc 原生触发）
function onNativeToggle(e: Event) {
  const toggleEvent = e as Event & { newState?: 'open' | 'closed' }
  const newState = toggleEvent.newState === 'open'
  if (newState !== isOpen.value) {
    if (props.open === undefined) internalOpen.value = newState
    emit('update:open', newState)
    if (newState) emit('open')
    else emit('close')
  }
}

// 响应外部 props.open 变化
watch(
  () => props.open,
  (val) => {
    if (val === undefined) return
    if (val) {
      openPopover()
    } else {
      closePopover()
    }
  },
)

// Hover 模式交互
function onMouseEnter() {
  if (props.trigger !== 'hover' || props.disabled) return
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => openPopover(), 120)
}

function onMouseLeave() {
  if (props.trigger !== 'hover') return
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => closePopover(), 150)
}

// 非原生 Popover 降级时的外部点击关闭
onClickOutside(rootEl, (event) => {
  // 如果原生 Popover 已在工作，由原生处理；否则通过 VueUse 兜底关闭
  if (popoverEl.value && typeof popoverEl.value.showPopover === 'function') return
  if (isOpen.value && !triggerEl.value?.contains(event.target as Node)) {
    closePopover()
  }
})

onMounted(() => {
  if (popoverEl.value) {
    popoverEl.value.addEventListener('toggle', onNativeToggle)
  }
  if (props.open) {
    nextTick(() => openPopover())
  }
})

onBeforeUnmount(() => {
  if (popoverEl.value) {
    popoverEl.value.removeEventListener('toggle', onNativeToggle)
  }
  if (hoverTimer) clearTimeout(hoverTimer)
})

defineExpose({
  open: openPopover,
  close: closePopover,
  toggle,
  isOpen,
})
</script>

<template>
  <div
    ref="rootEl"
    class="app-popover-root"
    :class="{ 'is-disabled': disabled }"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
  >
    <div
      ref="triggerEl"
      class="app-popover-trigger"
      :data-popover-anchor="anchorName"
      @click="trigger === 'click' && toggle()"
    >
      <slot
        :open="isOpen"
        :toggle="toggle"
        :close="closePopover"
        :target-id="popoverId"
        :anchor-name="anchorName"
      />
    </div>

    <div
      :id="popoverId"
      ref="popoverEl"
      popover="auto"
      :role="role || (ariaLabel ? 'region' : undefined)"
      :aria-label="ariaLabel"
      class="app-popover-panel surface"
      :class="{
        'is-open': isOpen,
        'has-arrow': arrow,
        [`side-${side}`]: true,
        [`align-${align}`]: true,
      }"
      :data-side="side"
    >
      <slot name="content" :close="closePopover" />
    </div>
  </div>
</template>

<style scoped>
.app-popover-root {
  display: inline-flex;
  position: relative;
  vertical-align: middle;
}

.app-popover-trigger {
  display: inline-flex;
  anchor-name: v-bind(anchorName);
}

.app-popover-panel {
  /* 重置原生 popover 默认样式 */
  margin: 0;
  inset: auto;
  padding: var(--space-2);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-0);
  box-shadow: var(--shadow-2);
  font-size: var(--text-sm);
  line-height: var(--leading-body);
  width: v-bind('props.width ? props.width : "max-content"');
  max-width: min(calc(100vw - 2rem), 32rem);
  max-height: min(80dvh, 36rem);
  overflow-y: auto;
  box-sizing: border-box;

  /* CSS Anchor 定位与顶层 */
  position: fixed;
  position-anchor: v-bind(anchorName);
  position-area: v-bind(positionArea);
  justify-self: v-bind(justifySelf);
  align-self: v-bind(alignSelf);
  position-try-fallbacks: flip-block, flip-inline;
  container-type: anchored;

  /* 进退场与微动效 */
  opacity: 0;
  scale: 0.98;
  transition:
    opacity var(--duration-1) var(--ease-out),
    scale var(--duration-1) var(--ease-out),
    overlay var(--duration-1) var(--ease-out) allow-discrete,
    display var(--duration-1) var(--ease-out) allow-discrete;
}

/* 展开态 */
.app-popover-panel:popover-open,
.app-popover-panel.is-open {
  opacity: 1;
  scale: 1;
}

/* 现代 @starting-style 入场过渡 */
@starting-style {
  .app-popover-panel:popover-open {
    opacity: 0;
    scale: 0.96;
  }
}

/* 针对不同方位的间距微调 */
.app-popover-panel[data-side='bottom'] {
  margin-top: var(--space-1-5);
}
.app-popover-panel[data-side='top'] {
  margin-bottom: var(--space-1-5);
}
.app-popover-panel[data-side='left'] {
  margin-right: var(--space-1-5);
}
.app-popover-panel[data-side='right'] {
  margin-left: var(--space-1-5);
}

/* 箭头指示 */
.app-popover-panel.has-arrow::before {
  content: '';
  position: absolute;
  width: 0.55rem;
  height: 0.55rem;
  background: var(--paper-0);
  border: 1px solid var(--line-strong);
  transform: rotate(45deg);
  pointer-events: none;
}

.app-popover-panel.side-bottom::before {
  top: -0.32rem;
  left: var(--space-4);
  border-bottom: none;
  border-right: none;
}

.app-popover-panel.side-top::before {
  bottom: -0.32rem;
  left: var(--space-4);
  border-top: none;
  border-left: none;
}

.app-popover-panel.align-end::before {
  left: auto;
  right: var(--space-4);
}

.app-popover-panel.align-center::before {
  left: 50%;
  right: auto;
  translate: -50% 0;
}

/* 锚点定位与 Popover 不可用时的绝对定位优雅降级 */
@supports not (anchor-name: --popover-anchor-test) {
  .app-popover-panel {
    position: absolute;
    z-index: 60;
  }

  .app-popover-panel:not(.is-open) {
    display: none;
  }

  .app-popover-panel.side-bottom.align-start {
    top: calc(100% + var(--space-1-5));
    left: 0;
    right: auto;
  }

  .app-popover-panel.side-bottom.align-end {
    top: calc(100% + var(--space-1-5));
    right: 0;
    left: auto;
  }

  .app-popover-panel.side-top.align-start {
    bottom: calc(100% + var(--space-1-5));
    left: 0;
    right: auto;
  }

  .app-popover-panel.side-top.align-end {
    bottom: calc(100% + var(--space-1-5));
    right: 0;
    left: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .app-popover-panel {
    transition: none;
    scale: 1 !important;
  }
}
</style>

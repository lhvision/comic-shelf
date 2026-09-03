<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, useId, watch } from 'vue'
import { useEventListener, useScrollLock } from '@vueuse/core'
import AmbientWatermark from '@/components/AmbientWatermark.vue'
import AppIcon from '@/components/AppIcon.vue'

/**
 * 通用对话框（Impeccable & HTML5 原生 <dialog> 顶层架构版）。
 * - 根容器采用原生 HTML <dialog> 元素，享受顶级 Top Layer 与原生无障碍焦点循环捕获；
 * - 严格采用 v-if="open" 与 <Transition>，确保关闭状态下物理脱离 DOM，绝不产生幽灵遮罩阻挡页面点击；
 * - 全功能 Props 契约：支持 closeOnBackdrop / closeOnEsc / showCloseButton / preventClose 精准控制交互自由度；
 * - 阻止关闭时触发轻量微弹提醒（triggerAttention），杜绝用户无感知迷茫；
 * - 视觉遮罩由内部 .modal-scrim 承接（::backdrop 设为透明），实现蒙层与面板 100% 同步平滑淡入淡出，彻底告别关闭黑屏闪退；
 * - 全部颜色/间距/圆角严格收敛于 tokens.css，无第三方 UI 库。
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    /** 无障碍标签（当未提供 title 且未提供 #title 插槽时使用） */
    ariaLabel?: string
    /** 主题变体：paper（默认纸间典藏） | reader（阅读器暗室） */
    variant?: 'paper' | 'reader'
    /** 尺寸规格：sm (26rem) | md (34rem, 默认) | lg (42rem) | xl (54rem) */
    size?: 'sm' | 'md' | 'lg' | 'xl'
    /** 是否渲染暗印水印（默认 paper 下为 true，reader 下为 false） */
    watermark?: boolean
    /** 是否允许点击遮罩关闭（默认 true） */
    closeOnBackdrop?: boolean
    /** 是否允许按下 Escape 键关闭（默认 true） */
    closeOnEsc?: boolean
    /** 是否显示右上角关闭图标按钮（默认 true） */
    showCloseButton?: boolean
    /** 是否强制阻止关闭（如数据保存中、关键批处理中；开启后遮罩与 Esc 均禁用且关闭按钮隐去，默认 false） */
    preventClose?: boolean
  }>(),
  {
    title: '',
    ariaLabel: undefined,
    variant: 'paper',
    size: 'md',
    watermark: undefined,
    closeOnBackdrop: true,
    closeOnEsc: true,
    showCloseButton: true,
    preventClose: false,
  },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  cancel: []
}>()

const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
const titleId = `modal-title-${uid}`
const dialogId = `modal-dialog-${uid}`
const dialogEl = ref<HTMLDialogElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const isShaking = ref(false)
const previousActiveElement = ref<HTMLElement | null>(null)
let shakeTimer: ReturnType<typeof setTimeout> | null = null

const showWatermark = computed(() => props.watermark ?? props.variant === 'paper')

const canCloseOnBackdrop = computed(() => !props.preventClose && props.closeOnBackdrop)
const canCloseOnEsc = computed(() => !props.preventClose && props.closeOnEsc)
const shouldShowCloseButton = computed(() => !props.preventClose && props.showCloseButton)

const closedByAttr = computed(() => {
  if (canCloseOnBackdrop.value && canCloseOnEsc.value) return 'any'
  if (canCloseOnEsc.value) return 'closerequest'
  return 'none'
})

const FOCUSABLE_SELECTOR =
  'button:not([disabled]):not([tabindex="-1"]), [href]:not([tabindex="-1"]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled]):not([tabindex="-1"]), textarea:not([disabled]):not([tabindex="-1"]), [tabindex]:not([tabindex="-1"])'

const isLocked = useScrollLock(typeof document !== 'undefined' ? document.body : null)

function triggerAttention() {
  if (isShaking.value) return
  isShaking.value = true
  if (shakeTimer) clearTimeout(shakeTimer)
  shakeTimer = setTimeout(() => {
    isShaking.value = false
  }, 380)
}

function restoreFocus() {
  if (previousActiveElement.value && typeof previousActiveElement.value.focus === 'function') {
    if (typeof document !== 'undefined' && document.body.contains(previousActiveElement.value)) {
      previousActiveElement.value.focus()
    }
    previousActiveElement.value = null
  }
}

function requestClose() {
  if (!props.open) return
  emit('update:open', false)
  emit('cancel')
  nextTick(() => {
    restoreFocus()
  })
}

function handleBackdropAction() {
  if (!canCloseOnBackdrop.value) {
    triggerAttention()
    return
  }
  requestClose()
}

// 当 open 为 true 时，记录当前焦点并提升至 Top Layer
async function openDialog() {
  if (
    typeof document !== 'undefined' &&
    document.activeElement instanceof HTMLElement &&
    (!dialogEl.value || !dialogEl.value.contains(document.activeElement))
  ) {
    previousActiveElement.value = document.activeElement
  }
  await nextTick()
  const dialog = dialogEl.value
  if (!dialog) return
  if (!dialog.open) {
    if (typeof dialog.showModal === 'function') {
      try {
        dialog.showModal()
      } catch {
        dialog.setAttribute('open', '')
      }
    } else {
      dialog.setAttribute('open', '')
    }
  }
  const focusables = Array.from(
    panel.value?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
  ).filter(
    (node) => node.offsetParent !== null || (node.checkVisibility ? node.checkVisibility() : true),
  )
  focusables[0]?.focus()
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      isLocked.value = true
      openDialog()
    } else {
      if (typeof document !== 'undefined') {
        const otherModals = document.querySelectorAll('dialog.modal-dialog[open]')
        const remaining = Array.from(otherModals).filter((m) => m !== dialogEl.value)
        if (remaining.length === 0) {
          isLocked.value = false
        }
      } else {
        isLocked.value = false
      }
      nextTick(() => {
        restoreFocus()
      })
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  restoreFocus()
  if (typeof document !== 'undefined') {
    // 检查页面是否还有其他未关闭的模态对话框，避免嵌套弹窗过早解除 body 滚动锁定
    const otherModals = document.querySelectorAll('dialog.modal-dialog[open]')
    if (otherModals.length === 0) {
      isLocked.value = false
    }
  } else {
    isLocked.value = false
  }
  if (shakeTimer) clearTimeout(shakeTimer)
})

// 原生 cancel 事件（如 ESC 键触发）
function onCancel(event: Event) {
  event.preventDefault()
  if (!canCloseOnEsc.value) {
    triggerAttention()
    return
  }
  requestClose()
}

// 原生 toggle / beforetoggle 事件（双向同步 Vue 状态与外部 commandfor 调用）
function onToggle(event: Event) {
  const toggleEvent = event as Event & { newState?: 'open' | 'closed' }
  if (toggleEvent.newState === 'closed' && props.open) {
    if (!canCloseOnEsc.value && !canCloseOnBackdrop.value) {
      triggerAttention()
      return
    }
    requestClose()
  } else if (toggleEvent.newState === 'open' && !props.open) {
    emit('update:open', true)
  }
}

// 原生 command 事件（响应 Invoker Commands API 的 command="close" 等指令）
function onCommand(event: Event) {
  const cmdEvent = event as Event & { command?: string }
  if (cmdEvent.command === 'close') {
    event.preventDefault()
    if (props.preventClose) {
      triggerAttention()
      return
    }
    requestClose()
  }
}

// 点击遮罩关闭兜底（针对 Safari 等尚未支持 closedby="any" 的环境）
function onDialogClick(event: MouseEvent) {
  if (event.target === dialogEl.value) {
    handleBackdropAction()
  }
}

// 键盘 Escape 与焦点辅助监听（兼顾测试环境与老旧浏览器无障碍）
useEventListener(window, 'keydown', (event: KeyboardEvent) => {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    if (!canCloseOnEsc.value) {
      triggerAttention()
      return
    }
    requestClose()
    return
  }
  if (event.key !== 'Tab') return
  const el = panel.value
  if (!el) return
  const focusables = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (node) => node.offsetParent !== null || (node.checkVisibility ? node.checkVisibility() : true),
  )
  if (focusables.length === 0) return
  const first = focusables[0]!
  const last = focusables[focusables.length - 1]!
  const active = document.activeElement as HTMLElement | null

  if (!active || !el.contains(active)) {
    event.preventDefault()
    if (event.shiftKey) {
      last.focus()
    } else {
      first.focus()
    }
  } else if (event.shiftKey && active === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <dialog
        v-if="open"
        :id="dialogId"
        ref="dialogEl"
        class="modal-root modal-dialog"
        :class="`is-${variant}`"
        :aria-labelledby="title || $slots.title ? titleId : undefined"
        :aria-label="!(title || $slots.title) ? ariaLabel || '对话框' : undefined"
        :closedby="closedByAttr"
        @cancel="onCancel"
        @click="onDialogClick"
        @toggle="onToggle"
        @command="onCommand"
        @submit.prevent
      >
        <div class="modal-scrim" aria-hidden="true" @click="handleBackdropAction" />
        <div
          ref="panel"
          class="modal-panel surface"
          :class="[`is-${variant}`, `size-${size}`, { 'is-shaking': isShaking }]"
          role="document"
        >
          <AmbientWatermark v-if="showWatermark" variant="modal" />

          <header class="modal-head">
            <h2 :id="titleId">
              <slot name="title">{{ title }}</slot>
            </h2>
            <button
              v-if="shouldShowCloseButton"
              class="modal-close icon-btn"
              type="button"
              aria-label="关闭"
              :commandfor="dialogId"
              command="close"
              @click="requestClose"
            >
              <AppIcon name="close" size="sm" />
            </button>
          </header>

          <div class="modal-body">
            <slot
              :close="requestClose"
              :dialog-id="dialogId"
              :close-command="{ commandfor: dialogId, command: 'close' }"
            />
          </div>

          <footer v-if="$slots.footer" class="modal-foot">
            <slot
              name="footer"
              :close="requestClose"
              :dialog-id="dialogId"
              :close-command="{ commandfor: dialogId, command: 'close' }"
            />
          </footer>
        </div>
      </dialog>
    </Transition>
  </Teleport>
</template>

<style scoped>
dialog:not([open]) {
  display: none !important;
}

.modal-root {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  padding: var(--space-5);
  margin: 0;
  width: 100vw;
  height: 100dvh;
  max-width: none;
  max-height: none;
  border: none;
  background: transparent;
  box-sizing: border-box;
  overflow: hidden;
  outline: none;
}

/* 原生 ::backdrop 在 Top Layer 维持透明，确保全屏遮罩动画与 Vue Transition 绝对同频，彻底消除黑屏闪退 */
.modal-root::backdrop {
  background: transparent;
}

/* 视觉与交互遮罩由内部 .modal-scrim 统一管理，天然享有 Vue <Transition> 的 opacity 进退场淡入淡出 */
.modal-scrim {
  position: absolute;
  inset: 0;
  background: var(--reader-scrim-strong);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.modal-panel {
  position: relative;
  z-index: 1;
  isolation: isolate;
  width: min(100%, 34rem);
  max-height: min(90dvh, 46rem);
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-3);
  box-shadow: var(--shadow-3);
  overflow: hidden;
  background: var(--paper-0);
}

/* 阻止关闭时的轻量微弹提醒 */
.modal-panel.is-shaking {
  animation: modal-shake 0.38s var(--ease-out);
}

@keyframes modal-shake {
  0%,
  100% {
    transform: scale(1) translateY(0);
  }
  20%,
  60% {
    transform: scale(1.015) translateY(-0.15rem);
  }
  40%,
  80% {
    transform: scale(0.995) translateY(0.1rem);
  }
}

/* 尺寸规格 */
.modal-panel.size-sm {
  width: min(100%, 26rem);
}

.modal-panel.size-md {
  width: min(100%, 34rem);
}

.modal-panel.size-lg {
  width: min(100%, 42rem);
}

.modal-panel.size-xl {
  width: min(100%, 54rem);
}

/* 主题变体：reader 暗室体系 */
.modal-panel.is-reader {
  background: var(--reader-bg);
  color: var(--reader-ink);
  border: 1px solid var(--reader-line);
}

.modal-panel.is-reader .modal-head {
  background: var(--reader-bg);
  border-bottom: 1px solid var(--reader-line-soft);
  color: var(--reader-ink);
}

.modal-panel.is-reader .modal-body {
  color: var(--reader-ink);
}

.modal-panel.is-reader .modal-foot {
  background: var(--reader-bg);
  border-top: 1px solid var(--reader-line-soft);
}

.modal-panel.is-reader .modal-close {
  background: var(--reader-surface-strong);
  border: 1px solid var(--reader-line);
  color: var(--reader-ink);
  box-shadow: none;
  backdrop-filter: none;
}

.modal-panel.is-reader .modal-close:hover {
  background: var(--reader-surface-hover);
  border-color: var(--reader-line-strong);
  color: var(--reader-ink);
}

.modal-panel.is-reader :deep(.btn-ghost),
.modal-panel.is-reader .btn-ghost {
  background: transparent;
  color: var(--reader-ink);
  border: 1px solid var(--reader-line-strong);
}

.modal-panel.is-reader :deep(.btn-ghost:hover:not(:disabled)),
.modal-panel.is-reader .btn-ghost:hover:not(:disabled) {
  background: var(--reader-surface-hover);
  border-color: var(--reader-line);
  color: var(--reader-ink);
}

/* 进退场分层动效：遮罩淡入淡出，面板弹入微降 */
.modal-enter-active {
  transition: opacity var(--duration-2) var(--ease-out);
}

.modal-leave-active {
  transition: opacity var(--duration-1) var(--ease-out);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-panel {
  animation: modal-pop var(--duration-2) var(--ease-out);
}

.modal-leave-active .modal-panel {
  transition:
    transform var(--duration-1) var(--ease-out),
    opacity var(--duration-1) var(--ease-out);
  transform: scale(0.985) translateY(0.35rem);
  opacity: 0;
}

.modal-head,
.modal-body,
.modal-foot {
  position: relative;
  z-index: 1;
}

.modal-head {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--line);
  background: var(--paper-0);
}

.modal-head h2 {
  font-size: var(--text-lg);
  line-height: var(--leading-tight);
}

.modal-close {
  flex: 0 0 auto;
}

.modal-close:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.modal-body {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--space-5);
  font-size: var(--text-sm);
  line-height: 1.7;
  color: var(--ink-1);
}

.modal-foot {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--line);
  background: var(--paper-0);
}

@keyframes modal-pop {
  from {
    opacity: 0;
    translate: 0 0.5rem;
    scale: 0.985;
  }
}

@media (prefers-reduced-motion: reduce) {
  .modal-enter-active,
  .modal-leave-active,
  .modal-panel {
    animation: none;
    transition: none;
  }
}

@media (max-width: 480px) {
  .modal-root {
    align-items: end;
    padding: 0;
  }

  .modal-panel {
    width: 100%;
    max-height: 92dvh;
    border-radius: var(--radius-3) var(--radius-3) 0 0;
  }

  .modal-panel.is-reader {
    border-bottom: none;
    border-left: none;
    border-right: none;
  }

  .modal-foot {
    padding-bottom: max(var(--space-5), env(safe-area-inset-bottom));
  }
}
</style>

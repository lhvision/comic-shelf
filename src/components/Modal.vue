<script setup lang="ts">
import { computed, nextTick, ref, useId, watch, onUnmounted } from 'vue'
import { useEventListener, useScrollLock } from '@vueuse/core'
import AmbientWatermark from '@/components/AmbientWatermark.vue'
import AppIcon from '@/components/AppIcon.vue'

/**
 * 通用对话框（Impeccable：fixed-header/fixed-footer/scrollable-body 版）。
 * - Teleport 到 body，遮罩点击 / Esc / 右上角 × 都会 emit('cancel')；
 * - 使用 VueUse useScrollLock 锁定 body 滚动，销毁时自动还原；
 * - 标题栏与底部操作栏固定在顶部与底部，超长内容区独立平滑滚动；
 * - 全部颜色/间距/圆角走 token，无第三方 UI 库。
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    /** 主题变体：paper（默认纸间典藏） | reader（阅读器暗室） */
    variant?: 'paper' | 'reader'
    /** 尺寸规格：sm (26rem) | md (34rem, 默认) | lg (42rem) | xl (54rem) */
    size?: 'sm' | 'md' | 'lg' | 'xl'
    /** 是否渲染暗印水印（默认 paper 下为 true，reader 下为 false） */
    watermark?: boolean
  }>(),
  {
    title: '',
    variant: 'paper',
    size: 'md',
    watermark: undefined,
  },
)

const emit = defineEmits<{ cancel: [] }>()

const titleId = `modal-title-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
const panel = ref<HTMLElement | null>(null)

const showWatermark = computed(() => props.watermark ?? props.variant === 'paper')

const FOCUSABLE_SELECTOR =
  'button:not([disabled]):not([tabindex="-1"]), [href]:not([tabindex="-1"]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled]):not([tabindex="-1"]), textarea:not([disabled]):not([tabindex="-1"]), [tabindex]:not([tabindex="-1"])'

const isLocked = useScrollLock(typeof document !== 'undefined' ? document.body : null)

watch(
  () => props.open,
  async (open) => {
    isLocked.value = open
    if (open) {
      await nextTick()
      const first = panel.value?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
      first?.focus()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  isLocked.value = false
})

useEventListener(window, 'keydown', (event: KeyboardEvent) => {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
    return
  }
  if (event.key !== 'Tab') return
  const el = panel.value
  if (!el) return
  const focusables = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
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
      <div v-if="open" class="modal-root" :class="`is-${variant}`">
        <div class="modal-scrim" @click="emit('cancel')" />
        <div
          ref="panel"
          class="modal-panel surface"
          :class="[`is-${variant}`, `size-${size}`]"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
        >
          <AmbientWatermark v-if="showWatermark" variant="modal" />

          <header class="modal-head">
            <h2 :id="titleId">
              <slot name="title">{{ title }}</slot>
            </h2>
            <button
              class="modal-close icon-btn"
              type="button"
              aria-label="关闭"
              @click="emit('cancel')"
            >
              <AppIcon name="close" size="sm" />
            </button>
          </header>

          <div class="modal-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="modal-foot">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-root {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  padding: var(--space-5);
}

.modal-scrim {
  position: absolute;
  inset: 0;
  background: var(--reader-scrim-strong);
}

.modal-panel {
  position: relative;
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
  -webkit-overflow-scrolling: touch;
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

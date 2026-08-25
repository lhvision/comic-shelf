<script setup lang="ts">
import { nextTick, ref, useId, watch, onUnmounted } from 'vue'
import { useEventListener, useScrollLock } from '@vueuse/core'
import AmbientWatermark from '@/components/AmbientWatermark.vue'

/**
 * 通用对话框（Impeccable：fixed-header/fixed-footer/scrollable-body 版）。
 * - Teleport 到 body，遮罩点击 / Esc / 右上角 × 都会 emit('cancel')；
 * - 使用 VueUse useScrollLock 锁定 body 滚动，销毁时自动还原；
 * - 标题栏与底部操作栏固定在顶部与底部，超长内容区独立平滑滚动；
 * - 全部颜色/间距/圆角走 token，无第三方 UI 库。
 */
const props = defineProps<{
  open: boolean
  title: string
}>()

const emit = defineEmits<{ cancel: [] }>()

const titleId = `modal-title-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
const panel = ref<HTMLElement | null>(null)

const isLocked = useScrollLock(typeof document !== 'undefined' ? document.body : null)

watch(
  () => props.open,
  async (open) => {
    isLocked.value = open
    if (open) {
      await nextTick()
      const first = panel.value?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )
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
  const focusables = Array.from(
    el.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  )
  if (focusables.length === 0) return
  const first = focusables[0]!
  const last = focusables[focusables.length - 1]!
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-root">
        <div class="modal-scrim" @click="emit('cancel')" />
        <div
          ref="panel"
          class="modal-panel surface"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
        >
          <AmbientWatermark variant="modal" />

          <header class="modal-head">
            <h2 :id="titleId">{{ title }}</h2>
            <button
              class="modal-close icon-btn"
              type="button"
              aria-label="关闭"
              @click="emit('cancel')"
            >
              ×
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

  .modal-foot {
    padding-bottom: max(var(--space-5), env(safe-area-inset-bottom));
  }
}
</style>

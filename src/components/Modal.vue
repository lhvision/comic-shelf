<script setup lang="ts">
import { nextTick, ref, useId, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import AmbientWatermark from '@/components/AmbientWatermark.vue'

/**
 * 通用对话框（Impeccable：danger/polish/adapt 版）。
 * - Teleport 到 body，遮罩点击 / Esc / 右上角 × 都会 emit('cancel')；
 * - 打开时锁 body 滚动、焦点落到面板内第一个可交互元素，Tab 焦点圈闭；
 * - 关闭时恢复 body 滚动。标题（h2）自动生成唯一 id 作 aria-labelledby。
 * - 全部颜色/间距/圆角走 token，无第三方 UI 库。
 */
const props = defineProps<{
  open: boolean
  title: string
}>()

const emit = defineEmits<{ cancel: [] }>()

const titleId = `modal-title-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`

const panel = ref<HTMLElement | null>(null)

watch(
  () => props.open,
  async (open, was) => {
    if (open) {
      document.body.style.overflow = 'hidden'
      await nextTick()
      const first = panel.value?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )
      first?.focus()
    } else if (was && !open) {
      document.body.style.overflow = ''
    }
  },
)

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
  animation: modal-fade var(--duration-2) var(--ease-out);
}

.modal-panel {
  position: relative;
  isolation: isolate;
  width: min(100%, 30rem);
  max-height: min(90dvh, 42rem);
  overflow: auto;
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  border-radius: var(--radius-3);
  box-shadow: var(--shadow-3);
  animation: modal-pop var(--duration-2) var(--ease-spring);
}

.modal-head,
.modal-body,
.modal-foot {
  position: relative;
  z-index: 1;
}

.modal-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: var(--space-3);
  padding-right: var(--space-2);
}

.modal-head h2 {
  font-size: var(--text-lg);
  line-height: var(--leading-tight);
}

.modal-close {
  flex: 0 0 auto;
}

.modal-body {
  font-size: var(--text-sm);
  line-height: 1.7;
  color: var(--ink-1);
}

.modal-foot {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--line);
}

@keyframes modal-fade {
  from {
    opacity: 0;
  }
}

@keyframes modal-pop {
  from {
    opacity: 0;
    translate: 0 0.5rem;
    scale: 0.985;
  }
}

@media (prefers-reduced-motion: reduce) {
  .modal-scrim,
  .modal-panel {
    animation: none;
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
}
</style>

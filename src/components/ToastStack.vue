<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { toasts, dismiss } = useToast()
</script>

<template>
  <div class="toast-stack" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="toast in toasts" :key="toast.id" class="toast-item" :data-tone="toast.tone">
        <span aria-hidden="true">{{ toast.tone === 'error' ? '✕' : '✓' }}</span>
        <div>
          <p>{{ toast.text }}</p>
          <button class="toast-close" @click="dismiss(toast.id)">知道了</button>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  right: max(1rem, env(safe-area-inset-right));
  bottom: max(1rem, env(safe-area-inset-bottom));
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.toast-close {
  margin-top: 0.35rem;
  padding: 0;
  background: transparent;
  color: var(--accent);
  font-size: var(--text-xs);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    translate var(--duration-2) var(--ease-out);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  translate: 0.75rem 0;
}
</style>

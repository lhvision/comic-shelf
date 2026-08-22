<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { toasts, dismiss } = useToast()
</script>

<template>
  <div class="toast-stack" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="toast in toasts" :key="toast.id" class="toast-item" :data-tone="toast.tone">
        <span class="toast-stamp" aria-hidden="true">{{ toast.tone === 'error' ? '✕' : '✓' }}</span>
        <div class="toast-content">
          <p class="toast-text">{{ toast.text }}</p>
          <button class="toast-close" type="button" @click="dismiss(toast.id)">知道了</button>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  right: max(var(--space-4), env(safe-area-inset-right));
  bottom: max(var(--space-5), env(safe-area-inset-bottom));
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  pointer-events: none;
}

.toast-item {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  max-width: min(26rem, calc(100vw - 2 * var(--space-4)));
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-0);
  box-shadow: var(--shadow-2);
  font-size: var(--text-sm);
}

.toast-item[data-tone='error'] {
  border-color: color-mix(in oklab, var(--accent) 45%, transparent);
  background: color-mix(in oklab, var(--accent-soft) 30%, var(--paper-0));
}

.toast-item[data-tone='info'] {
  border-color: var(--line-strong);
}

.toast-item[data-tone='success'] {
  border-color: color-mix(in oklab, var(--success) 45%, transparent);
  background: color-mix(in oklab, var(--success) 8%, var(--paper-0));
}

.toast-stamp {
  display: grid;
  place-items: center;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 50%;
  border: 1px solid currentColor;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  flex: 0 0 auto;
  margin-top: 0.1rem;
}

.toast-item[data-tone='error'] .toast-stamp {
  color: var(--accent-strong);
  border-color: var(--accent);
}

.toast-item[data-tone='success'] .toast-stamp {
  color: var(--success);
}

.toast-item[data-tone='info'] .toast-stamp {
  color: var(--ink-2);
}

.toast-content {
  min-width: 0;
  display: grid;
  gap: var(--space-1);
}

.toast-text {
  margin: 0;
  line-height: 1.5;
  word-break: break-word;
}

.toast-close {
  justify-self: start;
  padding: 0;
  background: transparent;
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
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
  translate: 1rem 0;
}
</style>

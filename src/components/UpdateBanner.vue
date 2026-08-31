<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { usePwaUpdate } from '@/composables/usePwaUpdate'
import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const { showPrompt, isUpdating, applyUpdate, dismissPrompt } = usePwaUpdate()

// 阅读器全屏沉浸模式下自动隐退，不遮挡画卷
const isReaderView = computed(() => route.name === 'reader')
const isVisible = computed(() => showPrompt.value && !isReaderView.value)
</script>

<template>
  <Transition name="update-banner">
    <aside
      v-if="isVisible"
      class="update-banner"
      role="alert"
      aria-live="polite"
      aria-label="纸间新卷本装订更新提示"
    >
      <div class="banner-inner">
        <span class="banner-stamp" aria-hidden="true">
          <AppIcon name="archive" size="xs" :stroke-width="1.8" />
        </span>

        <div class="banner-body">
          <p class="banner-title">纸间已有新卷本装订就绪</p>
          <span class="banner-sub font-mono">NEW ARCHIVE READY</span>
        </div>

        <div class="banner-actions">
          <button
            type="button"
            class="banner-btn apply-btn"
            :disabled="isUpdating"
            @click="applyUpdate"
          >
            <AppIcon
              name="refresh"
              size="xs"
              :stroke-width="1.8"
              :class="{ 'is-spinning': isUpdating }"
            />
            <span>{{ isUpdating ? '装订中…' : '立即装订' }}</span>
          </button>
          <button
            type="button"
            class="banner-btn dismiss-btn"
            title="稍后装订（收起至顶栏设备卡片）"
            aria-label="稍后装订，收起提示"
            @click="dismissPrompt"
          >
            <span>稍后</span>
          </button>
        </div>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.update-banner {
  position: fixed;
  left: 50%;
  bottom: max(var(--space-5), env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 70;
  pointer-events: none;
  width: min(calc(100vw - 2 * var(--space-4)), 32rem);
}

.banner-inner {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2-5) var(--space-3-5);
  background: var(--paper-0);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-3);
  box-shadow: var(--shadow-2);
  color: var(--ink-0);
  backdrop-filter: blur(8px);
}

.banner-stamp {
  display: grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: var(--paper-1);
  color: var(--accent-strong);
}

.banner-body {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.banner-title {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 500;
  line-height: var(--leading-tight);
  color: var(--ink-0);
}

.banner-sub {
  font-size: var(--text-caption);
  letter-spacing: 0.06em;
  color: var(--ink-2);
}

.banner-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 0 0 auto;
}

.banner-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  height: var(--control-xs);
  padding: 0 var(--space-3);
  border-radius: var(--radius-2);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
  white-space: nowrap;
}

.apply-btn {
  border: 1px solid color-mix(in oklab, var(--accent) 55%, transparent);
  background: color-mix(in oklab, var(--accent) 12%, var(--paper-0));
  color: var(--accent-strong);
  font-weight: 500;
}

.apply-btn:hover:not(:disabled) {
  background: color-mix(in oklab, var(--accent) 20%, var(--paper-0));
  border-color: var(--accent);
}

.apply-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.dismiss-btn {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-2);
}

.dismiss-btn:hover {
  background: var(--paper-1);
  color: var(--ink-1);
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.update-banner-enter-active,
.update-banner-leave-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out);
}

.update-banner-enter-from,
.update-banner-leave-to {
  opacity: 0;
  transform: translate(-50%, 1rem);
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import { useWindowScroll } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import AppTooltip from '@/components/AppTooltip.vue'

const props = withDefaults(
  defineProps<{
    /** 触发显示的滚动距离阈值（px） */
    threshold?: number
  }>(),
  {
    threshold: 400,
  },
)

const { y } = useWindowScroll()
const visible = computed(() => y.value > props.threshold)

function scrollToTop() {
  const prefersReduced =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  window.scrollTo({
    top: 0,
    behavior: prefersReduced ? 'auto' : 'smooth',
  })

  // 无障碍焦点平滑转移，防止 v-if 销毁后焦点丢失至 body
  const mainTarget = document.querySelector('main') || document.querySelector('.app-main')
  if (mainTarget instanceof HTMLElement) {
    if (!mainTarget.hasAttribute('tabindex')) {
      mainTarget.setAttribute('tabindex', '-1')
    }
    mainTarget.focus({ preventScroll: true })
  }
}
</script>

<template>
  <Transition name="back-to-top">
    <!-- 纯容器包裹，避免 role="region" 滥用 Landmark 列表 -->
    <div v-if="visible" class="back-to-top">
      <AppTooltip tip="回到顶部" side="top" align="center">
        <button type="button" class="back-to-top-btn" aria-label="回到顶部" @click="scrollToTop">
          <AppIcon name="arrow-up" size="lg" :stroke-width="2.2" />
        </button>
      </AppTooltip>
    </div>
  </Transition>
</template>

<style scoped>
.back-to-top {
  position: fixed;
  right: calc(var(--space-6) + env(safe-area-inset-right, 0px));
  bottom: calc(var(--space-6) + env(safe-area-inset-bottom, 0px));
  z-index: 30;
}

.back-to-top-btn {
  display: inline-grid;
  place-items: center;
  width: var(--control-md);
  height: var(--control-md);
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  background: var(--paper-1);
  color: var(--ink-0);
  box-shadow: var(--shadow-2);
  cursor: pointer;
  padding: 0;
  transition:
    transform var(--duration-1) var(--ease-spring),
    background-color var(--duration-1) var(--ease-out),
    border-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out);
}

.back-to-top-btn:hover {
  transform: translateY(-2px);
  background: var(--paper-0);
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: var(--shadow-3);
}

.back-to-top-btn:active {
  transform: translateY(0);
  box-shadow: var(--shadow-1);
}

.back-to-top-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* 动效：上浮淡入淡出 */
.back-to-top-enter-active,
.back-to-top-leave-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-spring);
}

.back-to-top-enter-from,
.back-to-top-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 640px) {
  .back-to-top {
    right: calc(var(--space-4) + env(safe-area-inset-right, 0px));
    bottom: calc(var(--space-4) + env(safe-area-inset-bottom, 0px));
  }
}

@media (prefers-reduced-motion: reduce) {
  .back-to-top-btn {
    transition: none;
  }
  .back-to-top-enter-active,
  .back-to-top-leave-active {
    transition: none;
  }
}
</style>

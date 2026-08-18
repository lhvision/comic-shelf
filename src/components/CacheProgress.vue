<script setup lang="ts">
import { computed } from 'vue'

/**
 * 书架卡片上的缓存进度条：三种状态一次讲清
 *  - idle     本地已缓存 N%
 *  - running  后台缓存中 N%（附呼吸动效，不抢戏）
 *  - complete 本地缓存 100%
 *
 * 颜色/间距全部走 tokens.css，动效只用一个 --duration + 一个 ease。
 */
const props = defineProps<{
  cached: number
  total: number
  /** 是否正在后台缓存（导入/缓存全部中） */
  running?: boolean
}>()

const safeTotal = computed(() => Math.max(props.total, 0))
const percent = computed(() =>
  safeTotal.value === 0 ? 0 : Math.min(100, Math.round((props.cached / safeTotal.value) * 100)),
)

const complete = computed(() => safeTotal.value > 0 && props.cached >= safeTotal.value)

const label = computed(() => {
  if (props.running) return `缓存中 ${percent.value}%`
  return `本地 ${percent.value}%`
})

const valueNow = computed(() => percent.value)
</script>

<template>
  <div
    class="cache-progress"
    :class="{
      'is-running': running,
      'is-complete': complete,
    }"
  >
    <div
      class="cache-progress__label"
      role="status"
      :aria-label="label"
      :data-running="running || undefined"
      :data-complete="complete || undefined"
    >
      <span v-if="running" class="cache-progress__dot" aria-hidden="true" />
      <span class="cache-progress__text">{{ label }}</span>
    </div>

    <div
      class="cache-progress__track"
      role="progressbar"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="valueNow"
      :aria-valuetext="label"
    >
      <span class="cache-progress__fill" :style="{ width: `${percent}%` }" />
    </div>
  </div>
</template>

<style scoped>
.cache-progress {
  display: grid;
  gap: var(--space-1);
  min-width: 6.5rem;
}

.cache-progress__label {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.4;
  color: var(--ink-2);
  white-space: nowrap;
}

.cache-progress__dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 999px;
  background: var(--accent);
  box-shadow: 0 0 0 0 color-mix(in oklab, var(--accent) 35%, transparent);
  animation: pulse var(--duration-2) var(--ease-out) infinite;
}

.cache-progress__label[data-running] {
  color: var(--accent-strong);
}

.cache-progress__label[data-complete] {
  color: var(--success);
}

.cache-progress__label[data-complete] .cache-progress__dot {
  display: none;
}

.cache-progress__track {
  position: relative;
  height: 3px;
  border-radius: 999px;
  background: var(--paper-2);
  overflow: hidden;
}

.cache-progress__fill {
  position: relative;
  display: block;
  height: 100%;
  min-width: 0;
  border-radius: inherit;
  background: var(--accent);
  transition: width var(--duration-3) var(--ease-out);
}

.cache-progress.is-complete .cache-progress__fill {
  background: var(--success);
}

/* 后台缓存中的斜纹扫描，只覆盖 fill，克制不花哨 */
.cache-progress.is-running .cache-progress__fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    transparent 20%,
    color-mix(in oklab, var(--paper-0) 55%, transparent) 50%,
    transparent 80%
  );
  translate: -100% 0;
  animation: stripe-shimmer 1.6s var(--ease-out) infinite;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in oklab, var(--accent) 32%, transparent);
  }
  55% {
    box-shadow: 0 0 0 5px color-mix(in oklab, var(--accent) 0%, transparent);
  }
}

@keyframes stripe-shimmer {
  to {
    translate: 100% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cache-progress__dot,
  .cache-progress.is-running .cache-progress__fill::after {
    animation: none;
  }
  .cache-progress__fill {
    transition: none;
  }
}
</style>

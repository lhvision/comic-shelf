<script setup lang="ts">
import { computed } from 'vue'
import AppProgressBar from '@/components/AppProgressBar.vue'

/**
 * 书架卡片/章节卡片上的缓存进度条：三种状态一次讲清
 *  - idle     本地已缓存 N%
 *  - running  后台缓存中 N%（附呼吸动效，不抢戏）
 *  - complete 本地缓存 100%
 *
 * 颜色/间距全部走 tokens.css，底层依托 AppProgressBar 获得 GPU 加速与现代 CSS 变量驱动。
 */
const props = defineProps<{
  cached: number
  total: number
  /** 是否正在后台缓存（导入/缓存全部中） */
  running?: boolean
}>()

const safeTotal = computed(() => Math.max(props.total, 0))
const percent = computed(() => {
  if (safeTotal.value === 0) return 0
  const clampedCached = Math.max(0, props.cached)
  return Math.min(100, Math.round((clampedCached / safeTotal.value) * 100))
})

const complete = computed(() => safeTotal.value > 0 && props.cached >= safeTotal.value)

const label = computed(() => {
  if (props.running) return `缓存中 ${percent.value}%`
  return `本地 ${percent.value}%`
})
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
      :data-running="running || undefined"
      :data-complete="complete || undefined"
    >
      <span v-if="running" class="cache-progress__dot" aria-hidden="true" />
      <span class="cache-progress__text">{{ label }}</span>
    </div>

    <AppProgressBar
      class="cache-progress__track"
      :value="props.cached"
      :max="safeTotal"
      variant="track"
      :color="complete ? 'success' : 'accent'"
      :animated="running && !complete"
      :label="label"
      :value-text="label"
    />
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

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in oklab, var(--accent) 32%, transparent);
  }
  55% {
    box-shadow: 0 0 0 5px color-mix(in oklab, var(--accent) 0%, transparent);
  }
}

@media (prefers-reduced-motion: reduce) {
  .cache-progress__dot {
    animation: none;
  }
}
</style>

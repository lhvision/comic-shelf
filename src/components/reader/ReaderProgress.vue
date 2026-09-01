<script setup lang="ts">
import { computed } from 'vue'

/**
 * 阅读器顶部进度条（3px 细线）。
 * 设计上把 "进度值 → transform" 的换算收进组件内部：
 * - 父级只传 `progress`（0~1）与 `invert`（RTL 时进度从右往左），
 * - 组件用 computed 把数值写成内联 transform（JS 兜底），
 * - 支持 scroll-timeline 的浏览器由父级的 `@supports` 动画接管覆盖同一条 transform。
 */
const props = defineProps<{
  progress: number
  /** RTL 横向模式：进度从右向左 */
  invert?: boolean
}>()

const spanStyle = computed(() => ({
  transform: `scaleX(${props.progress})`,
  transformOrigin: props.invert ? '100% 50%' : '0 50%',
}))
</script>

<template>
  <div
    class="reader-progress"
    :class="{ 'is-rtl': invert }"
    role="progressbar"
    :aria-valuenow="Math.round(progress * 100)"
    aria-valuemin="0"
    aria-valuemax="100"
    aria-label="阅读进度"
  >
    <span :style="spanStyle" />
  </div>
</template>

<style scoped>
.reader-progress {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  z-index: 6;
  height: 3px;
  background: var(--reader-surface-strong);
}

.reader-progress span {
  display: block;
  height: 100%;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: 0 50%;
}
</style>

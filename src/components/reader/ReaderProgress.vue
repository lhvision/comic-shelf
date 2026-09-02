<script setup lang="ts">
import AppProgressBar from '@/components/AppProgressBar.vue'

/**
 * 阅读器顶部进度条（3px 细线）。
 * - 父级只传 `progress`（0~1）与 `invert`（RTL 时进度从右往左），
 * - 底层由 AppProgressBar 统一渲染 GPU scaleX 细线与 ARIA 属性，
 * - 支持 scroll-timeline 的浏览器由 ReaderView 的 @supports 动画接管覆盖同一条 transform。
 */
defineProps<{
  progress: number
  /** RTL 横向模式：进度从右向左 */
  invert?: boolean
}>()
</script>

<template>
  <AppProgressBar
    class="reader-progress"
    :progress="progress"
    :invert="invert"
    variant="line"
    color="reader"
    label="阅读进度"
  />
</template>

<style scoped>
.reader-progress {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  z-index: 6;
}
</style>

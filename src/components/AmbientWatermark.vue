<script setup lang="ts">
import { computed } from 'vue'
import { useIllustrationPool } from '@/composables/useIllustrationPool'

const props = withDefaults(
  defineProps<{
    src?: string
    variant?: 'page' | 'modal'
  }>(),
  {
    src: undefined,
    variant: 'page',
  },
)

const { getRandomIllustration } = useIllustrationPool()
const illustrationSrc = computed(() => props.src || getRandomIllustration())
const watermarkUrl = computed(() => `url("${illustrationSrc.value}")`)
</script>

<template>
  <div class="ambient-watermark" :class="`is-${variant}`" aria-hidden="true" />
</template>

<style scoped>
.ambient-watermark {
  pointer-events: none;
  user-select: none;
  z-index: 0;
  overflow: hidden;
  background-image: v-bind(watermarkUrl);
  background-repeat: no-repeat;
  background-size: cover;
  background-position: center;
  transition: opacity var(--duration-2) var(--ease-out);
}

/* 页面级别背景：固定铺满整个浏览器视口（100vw × 100vh），全屏舒展覆盖 */
.ambient-watermark.is-page {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  /* 极浅纸质墨色融合，绝不干扰文字与看图 */
  opacity: 0.038;
  mix-blend-mode: multiply;
  filter: grayscale(12%) contrast(0.92);
  mask-image: radial-gradient(
    ellipse at 50% 50%,
    black 40%,
    rgb(0 0 0 / 70%) 75%,
    transparent 100%
  );
  -webkit-mask-image: radial-gradient(
    ellipse at 50% 50%,
    black 40%,
    rgb(0 0 0 / 70%) 75%,
    transparent 100%
  );
}

/* 弹窗级别背景：撑满整个弹窗卡片 100% 区域，全幅舒展铺满 */
.ambient-watermark.is-modal {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.048;
  mix-blend-mode: multiply;
  filter: grayscale(10%) contrast(0.92);
  mask-image: radial-gradient(
    ellipse at 50% 50%,
    black 50%,
    rgb(0 0 0 / 60%) 80%,
    transparent 100%
  );
  -webkit-mask-image: radial-gradient(
    ellipse at 50% 50%,
    black 50%,
    rgb(0 0 0 / 60%) 80%,
    transparent 100%
  );
}

@media (prefers-color-scheme: dark) {
  .ambient-watermark.is-page {
    opacity: 0.055;
    mix-blend-mode: screen;
    filter: brightness(0.85) contrast(0.92);
  }

  .ambient-watermark.is-modal {
    opacity: 0.068;
    mix-blend-mode: screen;
    filter: brightness(0.85) contrast(0.92);
  }
}
</style>

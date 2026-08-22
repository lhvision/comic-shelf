<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'

const props = withDefaults(
  defineProps<{
    src: string
    alt: string
    eager?: boolean
    loadingVariant?: number | string
  }>(),
  { eager: false, loadingVariant: undefined },
)

const rootEl = ref<HTMLElement | null>(null)
const imageEl = ref<HTMLImageElement | null>(null)
const loading = ref(true)
const failed = ref(false)
const retryKey = ref(0)

const displaySrc = computed(() => {
  if (retryKey.value === 0) return props.src
  const sep = props.src.includes('?') ? '&' : '?'
  return `${props.src}${sep}retry=${retryKey.value}`
})

function checkReadyState() {
  const img = imageEl.value
  if (!img || !img.complete) return
  if (img.naturalWidth > 0) {
    loading.value = false
    failed.value = false
  } else {
    loading.value = false
    failed.value = true
  }
}

function onLoad() {
  loading.value = false
  failed.value = false
}

function onError() {
  loading.value = false
  failed.value = true
}

function retry() {
  retryKey.value += 1
  loading.value = true
  failed.value = false
}

onMounted(checkReadyState)

watch(
  () => props.src,
  () => {
    retryKey.value = 0
    loading.value = true
    failed.value = false
  },
)
</script>

<template>
  <div
    ref="rootEl"
    class="comic-page-image"
    :data-state="loading ? 'loading' : failed ? 'error' : 'ready'"
  >
    <img
      ref="imageEl"
      class="comic-page-img"
      :src="displaySrc"
      :alt="alt"
      :loading="eager ? 'eager' : 'lazy'"
      decoding="async"
      @load="onLoad"
      @error="onError"
    />

    <ReaderLoadingState
      v-if="loading"
      class="page-loading-wrapper"
      :variant="loadingVariant"
      full-frame
    />

    <div v-else-if="failed" class="page-error" role="alert">
      <span>图片加载失败</span>
      <button type="button" @click="retry">重试</button>
    </div>
  </div>
</template>

<style scoped>
.comic-page-image {
  position: relative;
  width: 100%;
  height: 100%;
  display: grid;
  align-content: center;
  place-items: center;
  min-width: 0;
  min-height: 0;
}

.comic-page-image[data-state='loading'] {
  width: 100%;
  height: 100%;
  min-height: clamp(18rem, 60vh, 52rem);
}

.comic-page-img {
  max-width: 100%;
  max-height: 100%;
  opacity: 0;
  transition: opacity var(--duration-2) var(--ease-out);
}

.comic-page-image[data-state='ready'] .comic-page-img,
.comic-page-image[data-state='error'] .comic-page-img {
  opacity: 1;
}

.page-loading-wrapper {
  position: absolute;
  inset: 0;
  z-index: 3;
}

.page-error {
  position: absolute;
  top: 50%;
  left: 50%;
  translate: -50% -50%;
  display: grid;
  justify-items: center;
  gap: var(--space-2);
  color: var(--reader-muted, #938d80);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.page-error button {
  padding: 0.3rem 0.65rem;
  border: 1px solid rgb(255 255 255 / 18%);
  border-radius: var(--radius-1);
  background: rgb(255 255 255 / 8%);
  color: inherit;
  cursor: pointer;
  transition: background var(--duration-1) var(--ease-out);
}

.page-error button:hover {
  background: rgb(255 255 255 / 15%);
}
</style>

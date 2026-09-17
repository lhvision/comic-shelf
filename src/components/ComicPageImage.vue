<script setup lang="ts">
import { computed, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useTimeoutFn } from '@vueuse/core'
import { useOfflineSync } from '@/composables/useOfflineSync'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const props = withDefaults(
  defineProps<{
    src: string
    alt: string
    eager?: boolean
    loadingVariant?: number | string
  }>(),
  { eager: false, loadingVariant: undefined },
)

const imageEl = useTemplateRef<HTMLImageElement>('imageEl')
const loading = ref(true)
const failed = ref(false)
const retryKey = ref(0)
const autoRetryCount = ref(0)
const maxAutoRetries = 3
const retryDelay = ref(1200)
const naturalRatio = ref<string | null>(null)

const { isOnline } = useOfflineSync()

const { start: startAutoRetry, stop: stopAutoRetry } = useTimeoutFn(
  () => {
    hasEmittedReady = false
    retryKey.value += 1
  },
  retryDelay,
  { immediate: false },
)

const displaySrc = computed(() => {
  if (retryKey.value === 0) return props.src
  const sep = props.src.includes('?') ? '&' : '?'
  return `${props.src}${sep}retry=${retryKey.value}`
})

const emit = defineEmits<{
  ready: [ratio?: string | null]
}>()

let hasEmittedReady = false

function updateImageRatio() {
  const img = imageEl.value
  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    naturalRatio.value = `${img.naturalWidth} / ${img.naturalHeight}`
  }
}

function checkReadyState() {
  const img = imageEl.value
  if (!img || !img.complete) return
  if (img.naturalWidth > 0) {
    updateImageRatio()
    stopAutoRetry()
    autoRetryCount.value = 0
    loading.value = false
    failed.value = false
    if (!hasEmittedReady) {
      hasEmittedReady = true
      emit('ready', naturalRatio.value)
    }
  } else {
    handleError()
  }
}

function onLoad() {
  updateImageRatio()
  stopAutoRetry()
  autoRetryCount.value = 0
  loading.value = false
  failed.value = false
  if (!hasEmittedReady) {
    hasEmittedReady = true
    emit('ready', naturalRatio.value)
  }
}

function handleError() {
  // 离线断网时快速失败，不作无谓退避重试，直接展示缺页纸印
  if (!isOnline.value) {
    stopAutoRetry()
    loading.value = false
    failed.value = true
    return
  }

  if (autoRetryCount.value < maxAutoRetries) {
    autoRetryCount.value += 1
    // 递增退避延迟：1.2s、2.4s、3.6s（留足后端令牌桶以 3/s 速率回充配额的时间）
    retryDelay.value = autoRetryCount.value * 1200
    loading.value = true
    failed.value = false
    startAutoRetry()
  } else {
    loading.value = false
    failed.value = true
  }
}

function onError() {
  handleError()
}

function retry() {
  stopAutoRetry()
  autoRetryCount.value = 0
  hasEmittedReady = false
  retryKey.value += 1
  loading.value = true
  failed.value = false
}

onMounted(checkReadyState)

watch(
  () => props.src,
  () => {
    naturalRatio.value = null
    stopAutoRetry()
    autoRetryCount.value = 0
    hasEmittedReady = false
    retryKey.value = 0
    loading.value = true
    failed.value = false
  },
)

// 网络重获连接时，自动对先前因离线加载失败的图片执行重载，兑现「联网后将自动载入」体验承诺
watch(isOnline, (online, wasOnline) => {
  if (online && wasOnline === false && failed.value) {
    retry()
  }
})
</script>

<template>
  <div
    class="comic-page-image"
    :data-state="loading ? 'loading' : failed ? 'error' : 'ready'"
    :style="naturalRatio ? { aspectRatio: naturalRatio } : undefined"
  >
    <div
      class="comic-page-img-frame"
      :style="naturalRatio ? { aspectRatio: naturalRatio } : undefined"
    >
      <img
        ref="imageEl"
        class="comic-page-img"
        :src="displaySrc"
        :alt="alt"
        :loading="eager || retryKey > 0 ? 'eager' : 'lazy'"
        :fetchpriority="retryKey > 0 ? 'high' : undefined"
        decoding="async"
        @load="onLoad"
        @error="onError"
      />

      <slot :ready="!loading && !failed" />
    </div>

    <ReaderLoadingState
      v-if="loading"
      class="page-loading-wrapper"
      :variant="loadingVariant"
      full-frame
    />

    <div v-else-if="failed" class="page-error" :class="{ 'is-offline': !isOnline }" role="alert">
      <template v-if="!isOnline">
        <span class="offline-stamp">
          <AppIcon name="archive" size="xs" />
          <span>〔 画页未离线缓存 〕</span>
        </span>
        <span class="offline-sub">联网后将自动载入</span>
      </template>
      <template v-else>
        <span>图片加载失败</span>
        <AppButton variant="ghost" theme="reader" size="xs" type="button" @click="retry">
          重试
        </AppButton>
      </template>
    </div>
  </div>
</template>

<style scoped>
.comic-page-image {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 0;
  contain: layout style;
}

.comic-page-img-frame {
  position: relative;
  display: block;
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
}

.comic-page-image[data-state='loading'] {
  width: 100%;
  min-height: clamp(16rem, 55vh, 48rem);
  aspect-ratio: 0.72;
}

.comic-page-img {
  display: block;
  width: 100%;
  height: 100%;
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
  contain: strict;
}

.page-error {
  position: absolute;
  top: 50%;
  left: 50%;
  translate: -50% -50%;
  display: grid;
  justify-items: center;
  gap: var(--space-2);
  color: var(--reader-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  text-align: center;
  padding: var(--space-4);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--reader-bg) 85%, transparent);
}

.page-error.is-offline {
  border: 1px dashed var(--reader-line);
  padding: var(--space-6) var(--space-8);
}

.offline-stamp {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.05em;
}

.offline-sub {
  color: var(--reader-muted);
  font-size: var(--text-xs);
}

.page-error button {
  padding: var(--space-1-5) var(--space-2-5);
  border: 1px solid var(--reader-line);
  border-radius: var(--radius-1);
  background: var(--reader-surface);
  color: inherit;
  cursor: pointer;
  transition: background-color var(--duration-1) var(--ease-out);
}

.page-error button:hover {
  background: var(--reader-surface-hover);
}
</style>

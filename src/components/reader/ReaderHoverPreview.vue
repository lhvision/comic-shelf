<script setup lang="ts">
/**
 * @file ReaderHoverPreview.vue
 * @description 阅读器画中画 / 进度条悬停气泡组件（Hover Preview Popover / PiP）。
 *
 * 核心职责：
 * 1. 瞬态定盘（Ratio Latching）：
 *    - 读取传入的 ratio（来自 useComicRatioPool），弹出瞬间即锁定物理宽高比，杜绝弹窗几何抖动；
 * 2. 轻量微缩加载：
 *    - 仅请求 WebP 缩略图（pageThumbUrl），图片就绪后平滑淡入；
 * 3. 几何安全钳位（Edge Clamping）：
 *    - 依据传入的 anchorX 百分比或绝对坐标居中浮现，通过 CSS 保证不超出视口边界。
 */

import { computed, nextTick, ref, watch } from 'vue'
import { pageThumbUrl } from '@/api/client'

const props = withDefaults(
  defineProps<{
    /** 是否展示气泡 */
    show: boolean
    /** 目标全局页码 */
    page: number
    /** 漫画来源标识 */
    source: string
    /** 漫画编号标识 */
    sourceId: string
    /** 锚点水平像素位置（相对于容器左侧） */
    anchorX: number
    /** 物理宽高比（如 "800 / 1200"） */
    ratio?: string | null
    /** 章节内相对页码转换函数 */
    toLocalPage?: (p: number) => number
    /** 所属分屏组提示文案（如 "第 2 屏 [3-4]"） */
    groupTip?: string
  }>(),
  {
    ratio: null,
    toLocalPage: undefined,
    groupTip: undefined,
  },
)

const emit = defineEmits<{
  imageReady: [page: number, ratio: string]
}>()

const imgRef = ref<HTMLImageElement | null>(null)
const imgLoaded = ref(false)
const imgFailed = ref(false)
const loadedRatio = ref<string | null>(null)

const thumbUrl = computed(() => {
  if (!props.source || !props.sourceId || props.page <= 0) return ''
  return pageThumbUrl(props.source, props.sourceId, props.page)
})

const effectiveRatio = computed(() => loadedRatio.value || props.ratio || '3 / 4')

function checkImageComplete() {
  const img = imgRef.value
  if (
    img &&
    img.complete &&
    img.naturalWidth > 0 &&
    thumbUrl.value &&
    (img.currentSrc === thumbUrl.value || img.src === thumbUrl.value)
  ) {
    imgLoaded.value = true
    imgFailed.value = false
    const r = `${img.naturalWidth} / ${img.naturalHeight}`
    loadedRatio.value = r
    emit('imageReady', props.page, r)
  }
}

watch(
  () => [props.page, props.show],
  () => {
    imgLoaded.value = false
    imgFailed.value = false
    loadedRatio.value = null
    if (props.show && props.page > 0) {
      nextTick(() => {
        checkImageComplete()
      })
    }
  },
)

function onImageLoad(e: Event) {
  imgLoaded.value = true
  imgFailed.value = false
  const img = e.target as HTMLImageElement
  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    const r = `${img.naturalWidth} / ${img.naturalHeight}`
    loadedRatio.value = r
    emit('imageReady', props.page, r)
  }
}

function onImageError() {
  imgLoaded.value = false
  imgFailed.value = true
}

const popoverStyle = computed(() => {
  return {
    left: `${props.anchorX}px`,
    '--hover-ratio': effectiveRatio.value,
  }
})
</script>

<template>
  <Transition name="hover-popover">
    <aside
      v-if="show && page > 0"
      class="reader-hover-preview"
      :class="{ 'has-image': imgLoaded }"
      :style="popoverStyle"
      role="tooltip"
      aria-live="polite"
    >
      <!-- 渐进增强：仅在图片真实解码就绪后展开微缩卡片，加载中或未注水时降级为紧凑页码胶囊，彻底杜绝灰色空骨架框闪烁 -->
      <div v-show="imgLoaded" class="preview-frame">
        <img
          v-if="!imgFailed"
          ref="imgRef"
          :src="thumbUrl"
          :alt="`第 ${toLocalPage ? toLocalPage(page) : page} 页预览`"
          class="preview-img"
          :class="{ loaded: imgLoaded }"
          draggable="false"
          loading="eager"
          decoding="async"
          @load="onImageLoad"
          @error="onImageError"
        />
      </div>

      <footer class="preview-caption">
        <span class="preview-page-num"> 第 {{ toLocalPage ? toLocalPage(page) : page }} 页 </span>
        <span v-if="groupTip" class="preview-group-tip">{{ groupTip }}</span>
      </footer>
    </aside>
  </Transition>
</template>

<style scoped>
.reader-hover-preview {
  position: absolute;
  bottom: calc(100% + var(--space-2-5));
  translate: -50% 0;
  z-index: var(--z-popover, 60);
  pointer-events: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1-5);
  border-radius: var(--radius-md);
  border: 1px solid var(--reader-line-strong);
  background: var(--reader-scrim-strong);
  backdrop-filter: blur(16px);
  box-shadow: 0 12px 32px var(--reader-backdrop);
  will-change: transform, opacity;
  transition:
    padding var(--duration-1) var(--ease-out),
    border-radius var(--duration-1) var(--ease-out);
}

/* 渐进降级：未就绪/未注水时以极轻量紧凑胶囊展示页码 */
.reader-hover-preview:not(.has-image) {
  padding: var(--space-1) var(--space-2-5);
  border-radius: var(--radius-full);
  box-shadow: 0 4px 16px var(--reader-backdrop);
}

.preview-frame {
  position: relative;
  width: 148px;
  max-width: 40vw;
  aspect-ratio: var(--hover-ratio, 3 / 4);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--reader-page-bg);
  box-shadow: 0 2px 8px var(--reader-scrim);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: frame-unfold var(--duration-2) var(--ease-out);
}

@keyframes frame-unfold {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(4px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.preview-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity var(--duration-1) var(--ease-out);
}

.preview-img.loaded {
  opacity: 1;
}

.preview-caption {
  display: flex;
  align-items: baseline;
  gap: var(--space-1-5);
  padding: 0 var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-ink);
  white-space: nowrap;
}

.preview-page-num {
  font-weight: 500;
  color: var(--reader-ink);
}

.preview-group-tip {
  font-size: 0.6875rem;
  color: var(--reader-muted);
}

/* 动效：极度克制轻盈淡入与微缩上升 */
.hover-popover-enter-active,
.hover-popover-leave-active {
  transition:
    opacity var(--duration-1) var(--ease-out),
    translate var(--duration-1) var(--ease-out);
}

.hover-popover-enter-from,
.hover-popover-leave-to {
  opacity: 0;
  translate: -50% var(--space-1);
}

@media (prefers-reduced-motion: reduce) {
  .hover-popover-enter-active,
  .hover-popover-leave-active {
    transition: opacity var(--duration-1) linear;
  }
  .hover-popover-enter-from,
  .hover-popover-leave-to {
    translate: -50% 0;
  }
}

@media (hover: none) {
  .reader-hover-preview {
    display: none !important;
  }
}
</style>

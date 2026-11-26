<script setup lang="ts">
/**
 * ReaderPipContinuousStage.vue — 桌面悬浮阅览窗「条漫 / 适应宽度」竖向连续滚动长卷视口。
 * 负责滑动注水视窗（useReaderHydration）、rAF 局部邻域 + O(log N) 二分页码探测、
 * 外部跳页同步定位与程序化滚动锁保护。
 */
import { computed, nextTick, onScopeDispose, useTemplateRef, watch } from 'vue'
import { useTimeoutFn } from '@vueuse/core'
import { pageFileUrl } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import ComicPageImage from '@/components/ComicPageImage.vue'
import { useReaderHydration, type OrderedGroup } from '@/composables/useReaderHydration'
import type { Chapter } from '@/types'
import { binarySearchNearestIndex } from '@/utils/math'

const props = withDefaults(
  defineProps<{
    currentSource: string
    currentSourceId: string
    currentChapterId: string | null
    currentPage: number
    currentLocalPage: number
    scopedPages: number[]
    toLocalPage?: (page: number) => number
    seamless: boolean
    reducedMotion: boolean
    nextChapter: Chapter | null
    loadingVariant?: string | number
  }>(),
  {
    toLocalPage: undefined,
    loadingVariant: undefined,
  },
)

const emit = defineEmits<{
  syncPage: [page: number]
  selectChapter: [chapterId: string]
  openEnd: []
}>()

const continuousScrollEl = useTemplateRef<HTMLElement>('continuousScrollEl')
const comicKey = computed(() => `${props.currentSource}/${props.currentSourceId}`)
const continuousGroups = computed<OrderedGroup[]>(() =>
  props.scopedPages.map((page, index) => ({ pages: [page], index })),
)
const continuousActiveIndex = computed(() => {
  const idx = props.scopedPages.indexOf(props.currentPage)
  return idx >= 0 ? idx : Math.max(0, props.currentLocalPage - 1)
})
const { isGroupHydrated, getPageStyle, onPageImageReady } = useReaderHydration({
  orderedGroups: continuousGroups,
  currentGroupIndex: continuousActiveIndex,
  comicKey,
})

function formatLocalPage(page: number): number {
  return props.toLocalPage ? props.toLocalPage(page) : page
}

let continuousRafId: number | null = null
let isInternalScrollSync = false
let isProgrammaticContinuousScroll = false

const { start: startContinuousScrollUnlock, stop: stopContinuousScrollUnlock } = useTimeoutFn(
  () => {
    unlockContinuousScroll()
  },
  380,
  { immediate: false },
)

function unlockContinuousScroll() {
  isProgrammaticContinuousScroll = false
  stopContinuousScrollUnlock()
  continuousScrollEl.value?.removeEventListener('scrollend', unlockContinuousScroll)
}

function scrollContinuousToPage(page: number, behavior: ScrollBehavior = 'instant') {
  const el = continuousScrollEl.value
  if (!el) return
  const target = el.querySelector<HTMLElement>(`[data-pip-page="${page}"]`)
  if (!target) return
  if (behavior === 'smooth' && Math.abs(el.scrollTop - target.offsetTop) >= 1) {
    isProgrammaticContinuousScroll = true
    stopContinuousScrollUnlock()
    startContinuousScrollUnlock()
    const pipWin = el.ownerDocument.defaultView
    if (pipWin && 'onscrollend' in pipWin) {
      el.removeEventListener('scrollend', unlockContinuousScroll)
      el.addEventListener('scrollend', unlockContinuousScroll, { once: true })
    }
  } else {
    unlockContinuousScroll()
  }
  if (typeof el.scrollTo === 'function') {
    el.scrollTo({ top: target.offsetTop, left: 0, behavior })
  } else {
    el.scrollTop = target.offsetTop
  }
}

function scrollByStep(kind: 'line-down' | 'line-up' | 'page-down' | 'page-up') {
  const el = continuousScrollEl.value
  if (!el) return
  const pageStep = Math.max(120, Math.round(el.clientHeight * 0.85))
  const delta =
    kind === 'line-down'
      ? 72
      : kind === 'line-up'
        ? -72
        : kind === 'page-down'
          ? pageStep
          : -pageStep
  const behavior: ScrollBehavior = props.reducedMotion ? 'instant' : 'smooth'
  unlockContinuousScroll()
  if (typeof el.scrollBy === 'function') {
    el.scrollBy({ top: delta, left: 0, behavior })
  } else {
    el.scrollTop += delta
  }
}

function onContinuousScroll() {
  if (isProgrammaticContinuousScroll || continuousRafId !== null) return
  continuousRafId = requestAnimationFrame(() => {
    continuousRafId = null
    if (isProgrammaticContinuousScroll) return
    const el = continuousScrollEl.value
    const pages = props.scopedPages
    if (!el || pages.length === 0) return

    const pos = el.scrollTop
    const max = el.scrollHeight - el.clientHeight
    let matched = pages[0]!

    const evaluatePageRange = (pageNum: number) => {
      const node = el.querySelector<HTMLElement>(`[data-pip-page="${pageNum}"]`)
      if (!node) return null
      const top = node.offsetTop
      const height = node.offsetHeight
      const readLine = pos + Math.min(el.clientHeight * 0.4, height * 0.5)
      return {
        intersects: readLine >= top && readLine <= top + height,
        start: top,
        size: height,
        target: readLine,
      }
    }

    if (max > 0 && pos >= max - 16) {
      matched = pages[pages.length - 1]!
    } else if (pos <= 16) {
      matched = pages[0]!
    } else {
      const currentIdx = Math.max(0, pages.indexOf(props.currentPage))
      let found: number | null = null
      for (const offset of [0, 1, -1, 2, -2]) {
        const idx = currentIdx + offset
        if (idx < 0 || idx >= pages.length) continue
        if (evaluatePageRange(pages[idx]!)?.intersects) {
          found = pages[idx]!
          break
        }
      }
      if (found !== null) {
        matched = found
      } else {
        const matchedIdx = binarySearchNearestIndex(pages.length, currentIdx, (mid) =>
          evaluatePageRange(pages[mid]!),
        )
        matched = pages[matchedIdx] ?? matched
      }
    }

    if (matched !== props.currentPage) {
      isInternalScrollSync = true
      emit('syncPage', matched)
      void nextTick(() => {
        isInternalScrollSync = false
      })
    }
  })
}

watch(
  [comicKey, () => props.currentChapterId, () => props.currentPage],
  ([comic, chap, page], prevValues) => {
    if (page <= 0 || isInternalScrollSync) return
    const [prevComic, prevChap] = prevValues ?? []
    const shouldInstant = !prevValues || comic !== prevComic || chap !== prevChap
    scrollContinuousToPage(page, shouldInstant || props.reducedMotion ? 'instant' : 'smooth')
  },
  { flush: 'post', immediate: true },
)

onScopeDispose(() => {
  if (continuousRafId !== null) {
    cancelAnimationFrame(continuousRafId)
    continuousRafId = null
  }
  unlockContinuousScroll()
})

defineExpose({
  scrollByStep,
})
</script>

<template>
  <div
    ref="continuousScrollEl"
    class="pip-continuous-scroll"
    :data-seamless="seamless ? 'true' : undefined"
    @scroll.passive="onContinuousScroll"
    @wheel.passive="unlockContinuousScroll"
    @touchstart.passive="unlockContinuousScroll"
    @pointerdown.passive="unlockContinuousScroll"
  >
    <div
      v-for="(group, idx) in continuousGroups"
      :key="`${currentSource}/${currentSourceId}/${group.pages[0]}`"
      class="pip-continuous-page"
      :data-pip-page="group.pages[0]"
      :style="getPageStyle(group.pages[0]!)"
    >
      <ComicPageImage
        v-if="isGroupHydrated(idx)"
        :src="pageFileUrl(currentSource, currentSourceId, group.pages[0]!)"
        :alt="`第 ${formatLocalPage(group.pages[0]!)} 页`"
        :eager="idx <= 2"
        :loading-variant="loadingVariant"
        @ready="onPageImageReady(group.pages[0]!, $event)"
      />
      <div v-else class="pip-continuous-placeholder" aria-hidden="true">
        <span>{{ String(formatLocalPage(group.pages[0]!)).padStart(3, '0') }}</span>
      </div>
    </div>

    <div class="pip-continuous-end">
      <template v-if="nextChapter">
        <span class="pip-end-seal">〔 本话完 〕</span>
        <p class="pip-continuous-end-title">
          下一话：{{ nextChapter.title || `第 ${nextChapter.index} 話` }}
        </p>
        <AppButton
          theme="reader"
          variant="primary"
          size="xs"
          icon="arrow-right"
          icon-position="right"
          @click="$emit('selectChapter', nextChapter.id)"
        >
          <span>进入下一话</span>
        </AppButton>
      </template>
      <template v-else>
        <span class="pip-end-seal">〔 全卷完 · 归阁 〕</span>
        <p class="pip-continuous-end-title">已翻至本卷末页</p>
        <AppButton
          theme="reader"
          variant="soft"
          size="xs"
          icon="book-open"
          @click="$emit('openEnd')"
        >
          <span>查看接卷推荐</span>
        </AppButton>
      </template>
    </div>
  </div>
</template>

<style scoped>
.pip-continuous-scroll {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-gutter: stable;
  overscroll-behavior: contain;
}

.pip-continuous-page {
  width: 100%;
}

.pip-continuous-scroll:not([data-seamless='true']) .pip-continuous-page + .pip-continuous-page {
  margin-top: var(--space-2, 0.5rem);
}

.pip-continuous-scroll[data-seamless='true'] .pip-continuous-page + .pip-continuous-page {
  margin-top: -1px;
}

.pip-continuous-page :deep(.comic-page-image),
.pip-continuous-page :deep(.comic-page-img-frame) {
  width: 100%;
  height: auto;
  display: block;
}

.pip-continuous-page :deep(.comic-page-img) {
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: none;
  object-fit: contain;
  display: block;
}

.pip-continuous-scroll[data-seamless='true'] .pip-continuous-page :deep(.comic-page-img) {
  vertical-align: bottom;
}

.pip-continuous-placeholder {
  width: 100%;
  aspect-ratio: 0.72;
  display: grid;
  place-items: center;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-xs, 0.75rem);
  color: var(--reader-muted, #938d80);
  background: var(--reader-bg, #0d0e0c);
}

.pip-continuous-end {
  display: grid;
  justify-items: center;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-5, 1.25rem) var(--space-3, 0.75rem);
  text-align: center;
}

.pip-end-seal {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-accent, #e87a58);
  letter-spacing: 0.08em;
}

.pip-continuous-end-title {
  margin: 0;
  font-size: var(--text-xs, 0.75rem);
  color: var(--reader-ink, #eee7da);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

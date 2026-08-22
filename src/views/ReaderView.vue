<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEventListener, useFullscreen, usePreferredReducedMotion } from '@vueuse/core'
import { api, pageFileUrl } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useLastRead } from '@/composables/useLastRead'
import { useReaderSettings } from '@/composables/useReaderSettings'
import { useReaderPaging } from '@/composables/useReaderPaging'
import { useReaderChrome } from '@/composables/useReaderChrome'
import { useAutoTurn } from '@/composables/useAutoTurn'
import ComicPageImage from '@/components/ComicPageImage.vue'
import ReaderEndCard from '@/components/reader/ReaderEndCard.vue'
import ReaderHud from '@/components/reader/ReaderHud.vue'
import ReaderProgress from '@/components/reader/ReaderProgress.vue'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'
import ReaderSettingsPanel from '@/components/reader/ReaderSettingsPanel.vue'
import ReaderTopBar from '@/components/reader/ReaderTopBar.vue'
import type { Chapter, ComicDetail } from '@/types'

/**
 * 阅读器视图 —— 编排视图。
 * 分页切片下沉至 useReaderPaging，顶栏隐显下沉至 useReaderChrome，
 * 自动切换状态机下沉至 useAutoTurn，各功能面板作为独立纯展示子组件挂载。
 */

const route = useRoute()
const router = useRouter()
const { toast } = useToast()

const { settings, isWideViewport } = useReaderSettings()
const source = computed(() => String(route.params.source))
const sourceId = computed(() => String(route.params.sourceId))
const lastRead = useLastRead(source, sourceId)

const detail = ref<ComicDetail | null>(null)
const scrollEl = ref<HTMLElement | null>(null)
const currentPage = ref(1)
const currentGroupIndex = ref(0)
const settingsOpen = ref(false)
const loading = ref(true)
const progressValue = ref(0)
const loadingVariant = ref<1 | 2 | 3 | 4>((Math.floor(Math.random() * 4) + 1) as 1 | 2 | 3 | 4)
const reducedMotion = usePreferredReducedMotion()

/* ---------------- 章节作用域 ---------------- */
const scopeId = ref<string | null>(null)

watch(
  () => route.query.chapter,
  (q) => {
    scopeId.value = typeof q === 'string' && q ? q : null
  },
  { immediate: true },
)

// 遵守 DESIGN_NOTES §13 约束：Composable 返回值在 setup 顶层解构
const {
  scopedChapter,
  scopedPages,
  total,
  clampToScope,
  currentChapter,
  chapterLabel,
  chapters,
  currentChapterIndex,
  nextChapter,
  prevChapter,
  atChapterEnd,
  atChapterStart,
  showEndCard,
  pageGroups,
  orderedGroups,
  isVertical,
  rtlHorizontal,
  prevSymbol,
  nextSymbol,
  toLocalPage,
  currentGroupLabel,
  lastGroupIndex,
  atLastGroup,
  groupIndexForPage,
  groupFirstPage,
} = useReaderPaging({
  detail,
  scopeId,
  settings,
  currentPage,
  currentGroupIndex,
})

const { chromeVisible, showChromeTemporarily, scheduleChromeHide, toggleChrome } = useReaderChrome({
  settingsOpen,
})

const {
  autoTurnRemaining,
  autoTurnPaused,
  startAutoTurnCountdown,
  stopAutoTurnCountdown,
  resetAutoTurnCountdown,
  toggleAutoTurnPause,
} = useAutoTurn({
  settings,
  currentGroupIndex,
  lastGroupIndex,
  settingsOpen,
  onAdvance: advanceAutoTurn,
  onScheduleChromeHide: scheduleChromeHide,
})

function advanceAutoTurn() {
  const nextIndex = Math.min(currentGroupIndex.value + 1, lastGroupIndex.value)
  currentGroupIndex.value = nextIndex
  currentPage.value = groupFirstPage(nextIndex)
  const behavior = reducedMotion.value ? 'auto' : 'smooth'
  scrollToGroup(nextIndex, behavior)
}

/* ---------------- 分屏定位 ---------------- */
function scrollToGroup(groupIndex: number, behavior: ScrollBehavior = 'smooth') {
  const el = scrollEl.value
  if (!el) return
  const target = el.querySelector<HTMLElement>(`[data-group-index="${groupIndex}"]`)
  if (!target) return

  if (settings.mode === 'horizontal') {
    el.scrollTo({ left: target.offsetLeft, top: 0, behavior })
  } else {
    el.scrollTo({ left: 0, top: target.offsetTop, behavior })
  }
}

function goToGroup(groupIndex: number, behavior: ScrollBehavior = 'smooth') {
  const clamped = Math.min(Math.max(groupIndex, 0), Math.max(0, pageGroups.value.length - 1))
  currentGroupIndex.value = clamped
  currentPage.value = groupFirstPage(clamped)
  scrollToGroup(clamped, behavior)
  showChromeTemporarily()
  resetAutoTurnCountdown()
}

function goToPage(page: number, behavior: ScrollBehavior = 'smooth') {
  const clampedPage = clampToScope(page)
  const groupIndex = groupIndexForPage(clampedPage)
  currentPage.value = clampedPage
  currentGroupIndex.value = groupIndex
  scrollToGroup(groupIndex, behavior)
  showChromeTemporarily()
  resetAutoTurnCountdown()
}

/* ---------------- 滚动与键盘 ---------------- */
function onScroll() {
  const el = scrollEl.value
  if (!el) return

  const horizontal = settings.mode === 'horizontal'
  const rtl = horizontal && settings.direction === 'rtl'
  const position = horizontal ? el.scrollLeft : el.scrollTop
  const max = horizontal ? el.scrollWidth - el.clientWidth : el.scrollHeight - el.clientHeight
  const rawProgress = max <= 0 ? 1 : Math.min(1, Math.max(0, position / max))
  progressValue.value = rtl ? 1 - rawProgress : rawProgress

  const spreads = [...el.querySelectorAll<HTMLElement>('[data-group-index]')]
  let nearest = currentGroupIndex.value
  let bestDistance = Number.POSITIVE_INFINITY
  for (const spread of spreads) {
    const spreadPosition = horizontal ? spread.offsetLeft : spread.offsetTop
    const distance = Math.abs(spreadPosition - position)
    if (distance < bestDistance) {
      bestDistance = distance
      nearest = Number(spread.dataset.groupIndex)
    }
  }

  if (Number.isFinite(nearest) && nearest !== currentGroupIndex.value) {
    currentGroupIndex.value = nearest
    currentPage.value = groupFirstPage(nearest)
  }

  if (!settings.autoTurn) showChromeTemporarily()
  resetAutoTurnCountdown()
}

function onWheel(event: WheelEvent) {
  if (settings.mode !== 'horizontal') return
  const el = scrollEl.value
  if (!el) return

  if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return

  event.preventDefault()
  const factor = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1
  el.scrollBy({ left: event.deltaY * factor, behavior: 'auto' })
  if (!settings.autoTurn) showChromeTemporarily()
  resetAutoTurnCountdown()
}

function onKeydown(event: KeyboardEvent) {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
    return
  }
  if (event.target instanceof HTMLSelectElement) return

  if (settingsOpen.value) {
    if (event.key === 'Escape') {
      event.preventDefault()
      settingsOpen.value = false
    }
    return
  }

  const rtl = settings.mode === 'horizontal' && settings.direction === 'rtl'
  const nextLeft = rtl

  switch (event.key) {
    case 'ArrowRight':
      event.preventDefault()
      if (nextLeft) prevGroup()
      else nextGroup()
      break
    case 'ArrowLeft':
      event.preventDefault()
      if (nextLeft) nextGroup()
      else prevGroup()
      break
    case 'ArrowDown':
    case 'PageDown':
    case ' ':
      event.preventDefault()
      nextGroup()
      break
    case 'ArrowUp':
    case 'PageUp':
      event.preventDefault()
      prevGroup()
      break
    case 'Home':
      event.preventDefault()
      goToPage(1)
      break
    case 'End':
      event.preventDefault()
      goToPage(total.value)
      break
    case 'n':
    case 'N':
      goNextChapter()
      break
    case 'p':
    case 'P':
      goPrevChapter()
      break
    case 'f':
    case 'F':
      toggleFullscreen()
      break
    case 'Escape':
      event.preventDefault()
      backToDetail()
      break
  }
}

const { toggle: toggleFullscreen } = useFullscreen(document.documentElement)
useEventListener(window, 'keydown', onKeydown)

/* ---------------- 数据加载与监听 ---------------- */
onMounted(async () => {
  try {
    detail.value = await api.detail(source.value, sourceId.value)
    const initial = Number(route.params.page ?? 1)
    currentPage.value = clampToScope(initial)
    currentGroupIndex.value = groupIndexForPage(currentPage.value)
    loading.value = false

    await nextTick()
    scrollToGroup(currentGroupIndex.value, 'instant')
    scheduleChromeHide()
    preloadAround(currentPage.value)
    resetAutoTurnCountdown()
  } catch (e) {
    loading.value = false
    toast(e instanceof Error ? e.message : String(e), 'error')
    router.replace(`/comic/${source.value}/${sourceId.value}`)
  }
})

onBeforeUnmount(() => {
  lastRead.value = currentPage.value
})

watch(currentPage, (page) => {
  lastRead.value = page
  preloadAround(page)
})

watch(
  () => route.params.page,
  (value) => {
    const page = Number(value ?? 1)
    const pages = scopedPages.value
    if (!Number.isFinite(page) || pages.length === 0) return
    if (page < pages[0]! || page > pages[pages.length - 1]!) return
    if (page === currentPage.value) return
    goToPage(page, 'smooth')
  },
)

watch(
  () => `${settings.mode}|${settings.pagesPerView}|${settings.direction}`,
  async () => {
    currentGroupIndex.value = groupIndexForPage(currentPage.value)
    await nextTick()
    scrollToGroup(currentGroupIndex.value, 'instant')
    showChromeTemporarily()
    resetAutoTurnCountdown()
  },
)

function preloadAround(page: number) {
  const groupIndex = groupIndexForPage(page)
  const startGroup = Math.max(0, groupIndex - 1)
  const endGroup = Math.min(pageGroups.value.length - 1, groupIndex + 1)
  for (let group = startGroup; group <= endGroup; group += 1) {
    for (const targetPage of pageGroups.value[group] ?? []) {
      const image = new Image()
      image.src = pageFileUrl(source.value, sourceId.value, targetPage)
    }
  }
}

function prevGroup() {
  goToGroup(currentGroupIndex.value - 1)
}

function nextGroup() {
  goToGroup(currentGroupIndex.value + 1)
}

function chapterShortLabel(c: Chapter) {
  return c.title ? c.title : `第 ${c.index} 話`
}

function setScope(id: string, page: number) {
  scopeId.value = id
  const target = `/comic/${source.value}/${sourceId.value}/read/${page}?chapter=${encodeURIComponent(id)}`
  void router.replace(target)
}

function goNextChapter() {
  const c = nextChapter.value
  if (!c) return
  setScope(c.id, c.start)
  goToPage(c.start, 'smooth')
}

function goPrevChapter() {
  const c = prevChapter.value
  if (!c) return
  setScope(c.id, c.start + c.page_count - 1)
  goToPage(c.start + c.page_count - 1, 'smooth')
}

watch(
  () => scopeId.value,
  async () => {
    if (!detail.value) return
    const clamped = clampToScope(currentPage.value)
    if (clamped !== currentPage.value) currentPage.value = clamped
    currentGroupIndex.value = groupIndexForPage(currentPage.value)
    await nextTick()
    scrollToGroup(currentGroupIndex.value, 'instant')
    showChromeTemporarily()
    resetAutoTurnCountdown()
  },
)

const backTarget = computed(() => {
  const chapter = route.query.chapter
  if (chapter && typeof chapter === 'string') {
    return `/comic/${source.value}/${sourceId.value}/chapter/${encodeURIComponent(chapter)}`
  }
  return `/comic/${source.value}/${sourceId.value}`
})

function backToDetail() {
  router.push(backTarget.value)
}
</script>

<template>
  <div class="reader-view" :data-vertical="isVertical" :data-mode="settings.mode">
    <ReaderTopBar
      :title="detail?.meta.title ?? '载入中…'"
      :display-id="detail?.meta.display_id ?? ''"
      :chapter="chapterLabel"
      :hidden="!chromeVisible"
      @back="backToDetail"
      @open-settings="settingsOpen = true"
      @toggle-fullscreen="toggleFullscreen"
    />

    <div v-if="loading" class="reader-loading">
      <ReaderLoadingState :variant="loadingVariant" text="正在整理书页…" />
    </div>

    <main
      v-else
      ref="scrollEl"
      class="reader-scroll"
      :data-mode="settings.mode"
      :data-pages="settings.pagesPerView"
      :style="{ '--pages-per-view': settings.pagesPerView }"
      tabindex="0"
      @scroll.passive="onScroll"
      @wheel="onWheel"
      @mousemove="showChromeTemporarily"
    >
      <ReaderEndCard
        v-if="rtlHorizontal && showEndCard"
        snap
        class="reader-end-rtl"
        @back="backToDetail"
      />

      <section
        v-for="group in orderedGroups"
        :key="group.index"
        class="reader-spread"
        :data-group-index="group.index"
      >
        <article
          v-for="page in group.pages"
          :key="page"
          class="reader-page"
          :data-page="page"
          :id="`page-${page}`"
        >
          <div class="page-frame" :data-fit="settings.fit">
            <ComicPageImage
              :src="pageFileUrl(source, sourceId, page)"
              :alt="`第 ${toLocalPage(page)} 页`"
              :eager="toLocalPage(page) <= settings.pagesPerView * 3"
              :loading-variant="loadingVariant"
            />
          </div>
          <footer class="page-footer">
            <span>{{ String(toLocalPage(page)).padStart(3, '0') }}</span>
          </footer>
        </article>
      </section>

      <ReaderEndCard
        v-if="!rtlHorizontal && showEndCard"
        :snap="settings.mode === 'horizontal'"
        @back="backToDetail"
      />
    </main>

    <ReaderProgress :progress="progressValue" :invert="rtlHorizontal" />

    <button
      v-if="!loading && prevChapter && atChapterStart"
      class="reader-chapter-prev"
      type="button"
      @click="goPrevChapter"
    >
      <span class="reader-chapter-prev-title">← 上一话：{{ chapterShortLabel(prevChapter) }}</span>
      <span>本话首</span>
    </button>

    <button
      v-if="!loading && nextChapter && atChapterEnd"
      class="reader-chapter-next"
      type="button"
      @click="goNextChapter"
    >
      <span>本话完</span>
      <span class="reader-chapter-next-title">下一话：{{ chapterShortLabel(nextChapter) }} →</span>
    </button>

    <ReaderHud
      v-if="!loading"
      :auto-turn="settings.autoTurn"
      :at-last-group="atLastGroup"
      :auto-turn-paused="autoTurnPaused"
      :settings-open="settingsOpen"
      :auto-turn-remaining="autoTurnRemaining"
      :current-group-label="currentGroupLabel"
      :total="total"
      :prev-symbol="prevSymbol"
      :next-symbol="nextSymbol"
      :can-prev="currentGroupIndex > 0"
      :can-next="currentGroupIndex < pageGroups.length - 1"
      :hidden="!chromeVisible && !settings.autoTurn"
      @toggle-auto-turn-pause="toggleAutoTurnPause"
      @prev="prevGroup"
      @next="nextGroup"
    />

    <button
      class="reader-chrome-toggle"
      type="button"
      :aria-label="chromeVisible ? '隐藏工具栏' : '显示工具栏'"
      @click="toggleChrome"
    >
      {{ chromeVisible ? '—' : '☰' }}
    </button>

    <ReaderSettingsPanel v-if="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>

<style scoped>
.reader-view {
  --reader-chrome-h: clamp(4.4rem, 8vh, 6.2rem);
  --reader-gutter: clamp(var(--space-2), 2vw, var(--space-5));
  --reader-gap: clamp(var(--space-1), 1.4vw, var(--space-3));
  --reader-gap-tight: clamp(var(--space-1), 1.2vw, var(--space-3));
  --reader-frame-pad-v: var(--space-5);
  position: fixed;
  inset: 0;
  z-index: 50;
  background: var(--reader-bg);
  color: var(--reader-ink);
  overflow: hidden;
}

.reader-scroll {
  position: relative;
  height: 100dvh;
  overflow-y: auto;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 50% 0%, var(--reader-glow), transparent 38rem), var(--reader-bg);
  overscroll-behavior: contain;
  scroll-timeline-name: --reader-scroll;
  scroll-timeline-axis: block;
}

.reader-spread {
  content-visibility: auto;
  contain-intrinsic-block-size: auto 100dvh;
  contain-intrinsic-inline-size: auto 100vw;
}

/* ------------------------------ 竖向连续 ------------------------------ */
.reader-scroll[data-mode='vertical-continuous'] {
  display: block;
  scroll-snap-type: none;
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread {
  min-height: 0;
  display: grid;
  gap: var(--reader-gap-tight);
  grid-template-columns: repeat(var(--pages-per-view), minmax(0, 1fr));
  align-content: start;
  padding: 0 var(--reader-gutter);
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:first-child {
  padding-top: var(--reader-chrome-h);
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:not(:first-child) {
  padding-top: var(--reader-gap);
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:last-of-type {
  padding-bottom: var(--space-4);
}

/* ------------------------------ 竖向翻页 ------------------------------ */
.reader-scroll[data-mode='vertical-paged'] {
  display: block;
  scroll-snap-type: y proximity;
}

.reader-scroll[data-mode='vertical-paged'] .reader-spread {
  min-height: 100dvh;
  display: grid;
  gap: var(--reader-gap);
  grid-template-columns: repeat(var(--pages-per-view), minmax(0, 1fr));
  align-content: center;
  padding: var(--reader-chrome-h) var(--reader-gutter) var(--space-4);
  scroll-snap-align: start;
  scroll-snap-stop: always;
}

/* ------------------------------ 横向翻页 ------------------------------ */
.reader-scroll[data-mode='horizontal'] {
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  scrollbar-width: none;
}

.reader-scroll[data-mode='horizontal']::-webkit-scrollbar {
  display: none;
}

.reader-scroll[data-mode='horizontal'] .reader-spread {
  flex: 0 0 100%;
  min-width: 100%;
  height: 100dvh;
  display: grid;
  gap: var(--reader-gap-tight);
  grid-template-columns: repeat(var(--pages-per-view), minmax(0, 1fr));
  align-content: center;
  padding: var(--reader-chrome-h) var(--reader-gutter) var(--space-4);
  scroll-snap-align: start;
  scroll-snap-stop: always;
}

/* ------------------------------ 页面与图片 ------------------------------ */
.reader-page {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.page-frame {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 0;
  min-width: 0;
}

.page-frame :deep(.comic-page-img) {
  min-height: 40px;
  background: var(--reader-page-bg);
  box-shadow: var(--shadow-3);
}

/* 连续竖向 1 页：页面尺寸与竖向翻页一致，在视口内 contain */
.reader-scroll[data-mode='vertical-continuous'][data-pages='1']
  .page-frame
  :deep(.comic-page-image) {
  height: 100%;
}

/* 连续竖向 2/4 页：按列宽自然排版，避免页面内部留出整段空白 */
.reader-scroll[data-mode='vertical-continuous']:not([data-pages='1'])
  .page-frame
  :deep(.comic-page-image) {
  height: auto;
}

/* Loading 阶段预留最终高度，避免图片加载后滚动高度突变/卡住 */
.reader-scroll[data-mode='horizontal'] .page-frame :deep(.comic-page-image[data-state='loading']),
.reader-scroll[data-mode='vertical-paged']
  .page-frame
  :deep(.comic-page-image[data-state='loading']),
.reader-scroll[data-mode='vertical-continuous'][data-pages='1']
  .page-frame
  :deep(.comic-page-image[data-state='loading']) {
  min-height: 100%;
}

.reader-scroll[data-mode='vertical-continuous']:not([data-pages='1'])
  .page-frame
  :deep(.comic-page-image[data-state='loading']) {
  min-height: 0;
  aspect-ratio: 0.72;
  width: 100%;
}

.reader-scroll[data-mode='vertical-continuous'][data-pages='1']
  .page-frame[data-fit='width']
  :deep(.comic-page-img) {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.reader-scroll[data-mode='vertical-continuous'][data-pages='1']
  .page-frame[data-fit='height']
  :deep(.comic-page-img) {
  width: auto;
  max-width: 100%;
  height: 100%;
  object-fit: contain;
}

.reader-scroll[data-mode='vertical-continuous']:not([data-pages='1'])
  .page-frame[data-fit='width']
  :deep(.comic-page-img) {
  width: 100%;
  height: auto;
  max-height: none;
}

.reader-scroll[data-mode='vertical-continuous']:not([data-pages='1'])
  .page-frame[data-fit='height']
  :deep(.comic-page-img) {
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
}

/* 翻页模式：整页 contain，不裁切 */
.reader-scroll[data-mode='horizontal'] .page-frame,
.reader-scroll[data-mode='vertical-paged'] .page-frame,
.reader-scroll[data-mode='vertical-continuous'][data-pages='1'] .page-frame {
  height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
}

.reader-scroll[data-mode='horizontal'] .page-frame :deep(.comic-page-img),
.reader-scroll[data-mode='vertical-paged'] .page-frame :deep(.comic-page-img),
.reader-scroll[data-mode='vertical-continuous'][data-pages='1'] .page-frame :deep(.comic-page-img) {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.page-footer {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted);
  letter-spacing: 0.16em;
}

.reader-loading {
  display: grid;
  place-items: center;
  height: 100dvh;
  background: var(--reader-bg, #0d0c0a);
  padding: var(--space-4);
}

/* ---------------- 进度条（scroll-timeline 增强） ----------------
   ReaderProgress 组件提供 JS 兜底的 inline transform；
   支持 scroll() 的浏览器用以下动画接管同一属性（动画优先于 inline）。 */
@supports (animation-timeline: scroll()) {
  .reader-view {
    timeline-scope: --reader-scroll;
  }

  .reader-view[data-vertical='true'] :deep(.reader-progress span) {
    transform: none;
    animation: reader-progress linear both;
    animation-timeline: --reader-scroll;
    transform-origin: 0 50%;
  }
}

@keyframes reader-progress {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

/* ---------------- 顶栏折叠开关 ---------------- */
.reader-chrome-toggle {
  position: absolute;
  top: var(--space-2);
  left: 50%;
  z-index: 7;
  translate: -50% 0;
  width: var(--control-md);
  height: var(--control-md);
  display: grid;
  align-items: start;
  justify-items: center;
  padding-top: var(--space-1);
  border-radius: 999px;
  background: transparent;
  color: var(--reader-muted);
  font-size: var(--text-xs);
  line-height: 1;
}

.reader-chrome-toggle::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  width: var(--control-sm);
  height: 1rem;
  translate: -50% 0;
  border-radius: 999px;
  background: var(--reader-scrim-soft);
}

@media (min-width: 681px) {
  .reader-scroll[data-mode='vertical-continuous'][data-pages='1'] .reader-page,
  .reader-scroll[data-mode='vertical-paged'] .reader-page {
    height: calc(100dvh - var(--reader-chrome-h) + var(--space-1));
  }
}

@media (max-width: 680px) {
  .reader-chrome-toggle {
    top: var(--space-1);
  }
}

/* T08：跨话翻页横幅 —— 呆在话首的「← 上一话」、话末的「本话完 · 下一话 →」 */
.reader-chapter-next,
.reader-chapter-prev {
  position: absolute;
  left: 50%;
  bottom: max(calc(var(--space-6) * 1), env(safe-area-inset-bottom));
  translate: -50% 0;
  z-index: 7;
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-height: var(--control-md);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--accent);
  border-radius: 999px;
  background: var(--reader-scrim-strong);
  color: var(--reader-ink);
  transition:
    background var(--duration-2) var(--ease-out),
    color var(--duration-2) var(--ease-out);
}

.reader-chapter-next:hover,
.reader-chapter-prev:hover {
  background: var(--accent);
  color: var(--paper-0);
}

.reader-chapter-next-title,
.reader-chapter-prev-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60vw;
}
</style>

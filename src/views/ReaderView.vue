<script setup lang="ts">
/**
 * @file ReaderView.vue
 * @description 沉浸式阅读器主视图（纯编排视图，脚本严格 ≤150 行）。
 *
 * 状态机分层架构：
 * 1. 分页与作用域：`useReaderPaging`（多屏切片、全局/本地页码转换、跨话首尾探测）；
 * 2. 顶栏与 HUD 调度：`useReaderChrome`（延时隐藏与交互唤醒）；
 * 3. 导航与定位：`useReaderNavigation`（物理滚动、进度换算、滚轮映射、预加载）；
 * 4. 键盘与全屏：`useReaderKeyboard`（方向键/翻页键/切话键/全屏 F / ESC 返回）；
 * 5. 自动翻页状态机：`useAutoTurn`（倒计时、节拍器、页面可见性联动与暂停/继续）。
 */

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePreferredReducedMotion } from '@vueuse/core'
import { api, pageFileUrl } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useLastRead } from '@/composables/useLastRead'
import { useReaderSettings } from '@/composables/useReaderSettings'
import { useReaderPaging } from '@/composables/useReaderPaging'
import { useReaderChrome } from '@/composables/useReaderChrome'
import { useAutoTurn } from '@/composables/useAutoTurn'
import { useReaderNavigation } from '@/composables/useReaderNavigation'
import { useReaderKeyboard } from '@/composables/useReaderKeyboard'
import { useIllustrationPool } from '@/composables/useIllustrationPool'
import ComicPageImage from '@/components/ComicPageImage.vue'
import ReaderEndCard from '@/components/reader/ReaderEndCard.vue'
import ReaderHud from '@/components/reader/ReaderHud.vue'
import ReaderProgress from '@/components/reader/ReaderProgress.vue'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'
import ReaderSettingsPanel from '@/components/reader/ReaderSettingsPanel.vue'
import ReaderTopBar from '@/components/reader/ReaderTopBar.vue'
import type { ComicDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { toast } = useToast()

const { settings } = useReaderSettings()
const source = computed(() => String(route.params.source))
const sourceId = computed(() => String(route.params.sourceId))
const lastRead = useLastRead(source, sourceId)

const detail = ref<ComicDetail | null>(null)
const scrollEl = ref<HTMLElement | null>(null)
const currentPage = ref(1)
const currentGroupIndex = ref(0)
const settingsOpen = ref(false)
const loading = ref(true)
const { getRandomIllustration } = useIllustrationPool()
const loadingVariant = ref(getRandomIllustration())
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

const {
  scopedPages,
  total,
  clampToScope,
  chapterLabel,
  chapterShortLabel,
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
  progressValue,
  scrollToGroup,
  goToPage,
  prevGroup,
  nextGroup,
  onScroll,
  onWheel,
  preloadAround,
  goNextChapter,
  goPrevChapter,
} = useReaderNavigation({
  scrollEl,
  settings,
  currentPage,
  currentGroupIndex,
  pageGroups,
  lastGroupIndex,
  clampToScope,
  groupIndexForPage,
  groupFirstPage,
  showChromeTemporarily,
  // 倒计时重置回调仅在用户交互触发时执行，解耦初始化依赖
  resetAutoTurnCountdown: () => resetAutoTurnCountdown(),
  source,
  sourceId,
  nextChapter,
  prevChapter,
  scopeId,
  router,
})

function advanceAutoTurn() {
  const nextIndex = Math.min(currentGroupIndex.value + 1, lastGroupIndex.value)
  currentGroupIndex.value = nextIndex
  currentPage.value = groupFirstPage(nextIndex)
  const behavior = reducedMotion.value ? 'auto' : 'smooth'
  scrollToGroup(nextIndex, behavior)
}

const { autoTurnRemaining, autoTurnPaused, resetAutoTurnCountdown, toggleAutoTurnPause } =
  useAutoTurn({
    settings,
    currentGroupIndex,
    lastGroupIndex,
    settingsOpen,
    onAdvance: advanceAutoTurn,
    onScheduleChromeHide: scheduleChromeHide,
  })

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

function onReaderClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (target?.closest('button, a, input, select, textarea, [role="button"]')) {
    return
  }
  // 文本选区状态下不误触切换工具栏显隐
  if (window.getSelection()?.toString()) {
    return
  }
  toggleChrome()
}

const { toggleFullscreen } = useReaderKeyboard({
  settingsOpen,
  settings,
  total,
  goToPage,
  prevGroup,
  nextGroup,
  goNextChapter,
  goPrevChapter,
  backToDetail,
})

/* ---------------- 数据加载与监听 ---------------- */
let readerAbortController: AbortController | null = null

onMounted(async () => {
  if (readerAbortController) {
    readerAbortController.abort()
  }
  const controller = new AbortController()
  readerAbortController = controller

  try {
    const data = await api.detail(source.value, sourceId.value, { signal: controller.signal })
    if (controller.signal.aborted) return
    detail.value = data
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
    if (controller.signal.aborted) return
    loading.value = false
    toast(e instanceof Error ? e.message : String(e), 'error')
    router.replace(`/comic/${source.value}/${sourceId.value}`)
  } finally {
    if (readerAbortController === controller) {
      readerAbortController = null
    }
  }
})

onBeforeUnmount(() => {
  if (readerAbortController) {
    readerAbortController.abort()
    readerAbortController = null
  }
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
      <ReaderLoadingState :variant="loadingVariant" text="正在整理书页…" full-frame />
    </div>

    <main
      v-else
      ref="scrollEl"
      class="reader-scroll"
      :data-mode="settings.mode"
      :data-pages="settings.pagesPerView"
      tabindex="0"
      @scroll.passive="onScroll"
      @wheel="onWheel"
      @mousemove="showChromeTemporarily"
      @click="onReaderClick"
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
  --pages-per-view: v-bind('settings.pagesPerView');
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

/* ------------------------------ 页面与图片 ------------------------------ */
.reader-page {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.page-frame {
  width: 100%;
  min-height: 0;
  min-width: 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.page-frame :deep(.comic-page-img) {
  min-height: 40px;
  background: var(--reader-page-bg);
  box-shadow: var(--shadow-3);
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
  justify-items: center;
  padding: 0 var(--reader-gutter);
  max-width: var(--content-width);
  margin-inline: auto;
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:first-child {
  padding-top: max(
    var(--reader-chrome-h),
    calc(var(--header-h) + env(safe-area-inset-top, 0px) + var(--space-2))
  );
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:not(:first-child) {
  padding-top: var(--reader-gap);
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:last-of-type {
  padding-bottom: max(var(--space-6), env(safe-area-inset-bottom, 0px));
}

.reader-scroll[data-mode='vertical-continuous'] .reader-page {
  width: 100%;
  height: auto;
}

.reader-scroll[data-mode='vertical-continuous'] .page-frame {
  height: auto;
}

/* 连续模式 适应宽度：全宽纵向下流 */
.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='width']
  :deep(.comic-page-image) {
  width: 100%;
  height: auto;
}

.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='width']
  :deep(.comic-page-img) {
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: none;
  object-fit: contain;
}

/* 连续模式 适应高度：高度受限，保持整页入目 */
.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='height']
  :deep(.comic-page-image) {
  width: 100%;
  height: auto;
  display: flex;
  justify-content: center;
}

.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='height']
  :deep(.comic-page-img) {
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
  object-fit: contain;
}

/* ------------------------------ 竖向翻页 ------------------------------ */
.reader-scroll[data-mode='vertical-paged'] {
  display: block;
  scroll-snap-type: y proximity;
}

.reader-scroll[data-mode='vertical-paged'] .reader-spread {
  height: 100dvh;
  min-height: 100dvh;
  display: grid;
  gap: var(--reader-gap);
  grid-template-columns: repeat(var(--pages-per-view), minmax(0, 1fr));
  align-content: center;
  justify-items: center;
  padding: var(--reader-chrome-h) var(--reader-gutter) var(--space-4);
  scroll-snap-align: start;
  scroll-snap-stop: always;
  box-sizing: border-box;
}

.reader-scroll[data-mode='vertical-paged'] .reader-page {
  height: 100%;
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
  width: 100%;
  justify-content: center;
}

.reader-scroll[data-mode='vertical-paged'] .page-frame {
  flex: 1;
  height: 100%;
}

.reader-scroll[data-mode='vertical-paged'] .page-frame :deep(.comic-page-image) {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.reader-scroll[data-mode='vertical-paged'] .page-frame :deep(.comic-page-img) {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
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
  justify-items: center;
  padding: var(--reader-chrome-h) var(--reader-gutter) var(--space-4);
  scroll-snap-align: start;
  scroll-snap-stop: always;
  box-sizing: border-box;
}

.reader-scroll[data-mode='horizontal'] .reader-page {
  height: 100%;
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
  width: 100%;
  justify-content: center;
}

.reader-scroll[data-mode='horizontal'] .page-frame {
  flex: 1;
  height: 100%;
}

.reader-scroll[data-mode='horizontal'] .page-frame :deep(.comic-page-image) {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.reader-scroll[data-mode='horizontal'] .page-frame :deep(.comic-page-img) {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
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

@media (max-width: 680px) {
  .reader-chapter-next,
  .reader-chapter-prev {
    bottom: calc(
      var(--control-md) + max(var(--space-4), env(safe-area-inset-bottom)) + var(--space-2)
    );
  }
}
</style>

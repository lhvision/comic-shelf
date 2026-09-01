<script setup lang="ts">
/**
 * @file ReaderView.vue
 * @description 沉浸式阅读器主视图（纯编排视图，脚本严格 ≤150 行）。
 *
 * 状态机分层架构：
 * 1. 数据流与生命周期：`useReaderData`（元数据加载、竞态隔离、URL 参数同步与返回路径）；
 * 2. 分页与作用域：`useReaderPaging`（多屏切片、全局/本地页码转换、跨话首尾探测）；
 * 3. 顶栏与 HUD 调度：`useReaderChrome`（延时隐藏与交互唤醒）；
 * 4. 导航与定位：`useReaderNavigation`（物理滚动、进度换算、滚轮映射、预加载）；
 * 5. 键盘与全屏：`useReaderKeyboard`（方向键/翻页键/切话键/全屏 F / ESC 返回）；
 * 6. 自动翻页状态机：`useAutoTurn`（倒计时、节拍器、页面可见性联动与暂停/继续）。
 */

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePreferredReducedMotion, useToggle } from '@vueuse/core'
import { useReaderSettings } from '@/composables/useReaderSettings'
import { useReaderPaging } from '@/composables/useReaderPaging'
import { useReaderChrome } from '@/composables/useReaderChrome'
import { useAutoTurn } from '@/composables/useAutoTurn'
import { useReaderNavigation } from '@/composables/useReaderNavigation'
import { useReaderKeyboard } from '@/composables/useReaderKeyboard'
import { useReaderData } from '@/composables/useReaderData'
import ReaderTopBar from '@/components/reader/ReaderTopBar.vue'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'
import ReaderViewport from '@/components/reader/ReaderViewport.vue'
import ReaderProgress from '@/components/reader/ReaderProgress.vue'
import ReaderChapterBanners from '@/components/reader/ReaderChapterBanners.vue'
import ReaderHud from '@/components/reader/ReaderHud.vue'
import ReaderSettingsPanel from '@/components/reader/ReaderSettingsPanel.vue'

const route = useRoute()
const router = useRouter()
const { settings } = useReaderSettings()
const currentPage = ref(1)
const currentGroupIndex = ref(0)
const [settingsOpen] = useToggle(false)
const reducedMotion = usePreferredReducedMotion()

const viewportRef = ref<{ scrollEl: HTMLElement | null } | null>(null)
const scrollEl = computed(() => viewportRef.value?.scrollEl ?? null)
const userInteracted = ref(false)

const { detail, loading, loadingVariant, source, sourceId, scopeId, backToDetail, lastRead } =
  useReaderData({
    onLoaded: async () => {
      const rawParam = route.params.page
      const rawNum =
        typeof rawParam === 'string'
          ? Number(rawParam)
          : Array.isArray(rawParam)
            ? Number(rawParam[0])
            : Number.NaN
      const initial =
        Number.isFinite(rawNum) && rawNum > 0 ? rawNum : lastRead.value || scopedPages.value[0] || 1
      currentPage.value = clampToScope(initial)
      currentGroupIndex.value = groupIndexForPage(currentPage.value)

      await nextTick()
      scrollToGroup(currentGroupIndex.value, 'instant')
      scheduleChromeHide()
      preloadAround(currentPage.value)
      resetAutoTurnCountdown()
    },
  })

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
  pageGroups,
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
  recalibrateTargetOffset,
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
  resetAutoTurnCountdown: () => resetAutoTurnCountdown(),
  source,
  sourceId,
  nextChapter,
  prevChapter,
  scopeId,
  router,
})

function onPageReady(_page: number) {
  if (!userInteracted.value && settings.mode === 'vertical-continuous') {
    recalibrateTargetOffset(currentGroupIndex.value)
  }
}

function onViewportWheel(event: WheelEvent) {
  userInteracted.value = true
  onWheel(event)
}

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

/* ---------------- 页面响应式联动与历史同步 ---------------- */
watch(currentPage, (page) => {
  lastRead.value = page
  preloadAround(page)
})

onBeforeUnmount(() => {
  lastRead.value = currentPage.value
})

watch(
  () => route.params.page,
  (value) => {
    if (loading.value) return
    const rawNum =
      typeof value === 'string'
        ? Number(value)
        : Array.isArray(value)
          ? Number(value[0])
          : Number.NaN
    const page =
      Number.isFinite(rawNum) && rawNum > 0 ? rawNum : lastRead.value || scopedPages.value[0] || 1
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

function onReaderClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (target?.closest('button, a, input, select, textarea, [role="button"]')) {
    return
  }
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
  onUserInteract: () => {
    userInteracted.value = true
  },
})
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

    <ReaderViewport
      v-else
      ref="viewportRef"
      :settings="settings"
      :source="source"
      :source-id="sourceId"
      :ordered-groups="orderedGroups"
      :show-end-card="showEndCard"
      :rtl-horizontal="rtlHorizontal"
      :loading-variant="loadingVariant"
      :to-local-page="toLocalPage"
      @scroll="onScroll"
      @wheel="onViewportWheel"
      @user-interact="userInteracted = true"
      @page-ready="onPageReady"
      @mousemove="showChromeTemporarily"
      @reader-click="onReaderClick"
      @back-to-detail="backToDetail"
    />

    <ReaderProgress :progress="progressValue" :invert="rtlHorizontal" />

    <ReaderChapterBanners
      v-if="!loading"
      :prev-chapter="prevChapter"
      :next-chapter="nextChapter"
      :at-chapter-start="atChapterStart"
      :at-chapter-end="atChapterEnd"
      :chapter-short-label="chapterShortLabel"
      :mode="settings.mode"
      @prev-chapter="goPrevChapter"
      @next-chapter="goNextChapter"
    />

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

    <ReaderSettingsPanel :open="settingsOpen" @close="settingsOpen = false" />
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

  /* 纵向与横向 LTR 模式：从左向右生长 */
  .reader-view :deep(.reader-progress span) {
    transform: none;
    animation: reader-progress 1ms linear both;
    animation-timeline: --reader-scroll;
    transform-origin: 0 50%;
  }

  /* 横向 RTL 日漫模式：从右向左生长 */
  .reader-view[data-mode='horizontal'] :deep(.reader-progress.is-rtl span) {
    transform: none;
    animation: reader-progress-rtl 1ms linear both;
    animation-timeline: --reader-scroll;
    transform-origin: 100% 50%;
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

@keyframes reader-progress-rtl {
  from {
    transform: scaleX(1);
  }
  to {
    transform: scaleX(0);
  }
}
</style>

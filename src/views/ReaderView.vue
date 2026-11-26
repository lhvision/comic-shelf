<script setup lang="ts">
/**
 * @file ReaderView.vue - 沉浸式阅读器主视图（纯编排视图，脚本严格 ≤150 行）
 */

import { computed, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useMediaQuery, useScrollLock, useToggle } from '@vueuse/core'
import { REDUCED_MOTION_QUERY } from '@/utils/is'
import { pageFileUrl } from '@/api/client'
import { useReaderSettings } from '@/composables/useReaderSettings'
import { useReaderPaging } from '@/composables/useReaderPaging'
import { useReaderChrome } from '@/composables/useReaderChrome'
import { useAutoTurn } from '@/composables/useAutoTurn'
import { useReaderNavigation } from '@/composables/useReaderNavigation'
import { useReaderData } from '@/composables/useReaderData'
import { useReaderBubble } from '@/composables/useReaderBubble'
import { useReaderCompletion } from '@/composables/useReaderCompletion'
import { useReaderInteraction } from '@/composables/useReaderInteraction'
import { useReadingSession } from '@/composables/useReadingSession'
import ReaderTopBar from '@/components/reader/ReaderTopBar.vue'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'
import ReaderViewport from '@/components/reader/ReaderViewport.vue'
import ReaderProgress from '@/components/reader/ReaderProgress.vue'
import ReaderChapterBanners from '@/components/reader/ReaderChapterBanners.vue'
import ReaderHud from '@/components/reader/ReaderHud.vue'
import ReaderFloatingPill from '@/components/reader/ReaderFloatingPill.vue'
import ReaderSettingsPanel from '@/components/reader/ReaderSettingsPanel.vue'
import ReaderFilmstrip from '@/components/reader/ReaderFilmstrip.vue'
import ReaderPipWindow from '@/components/reader/ReaderPipWindow.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const readerSettings = useReaderSettings()
const { settings } = readerSettings

const readerBubble = useReaderBubble(route, router)
const { targetBubble } = readerBubble
const initP = Number.parseInt(String(route.params.page || route.query.page), 10)
const currentPage = ref(initP > 0 ? initP : 1)
const currentGroupIndex = ref(initP > 0 ? Math.max(0, initP - 1) : 0)
const userInteracted = ref(false)
const [settingsOpen] = useToggle(false)
const [filmstripOpen, toggleFilmstrip] = useToggle(false)
const pipOpen = ref(false)
const pipBlocked = ref(false)
const reducedMotion = useMediaQuery(REDUCED_MOTION_QUERY)
const viewportRef = useTemplateRef<{ scrollEl: HTMLElement | null }>('viewportRef')
const scrollEl = computed(() => viewportRef.value?.scrollEl ?? null)

// 移动端全屏视口锁：进入阅读器时锁定 body 滚动防止滚动穿透与顶栏错位
const isBodyLocked = useScrollLock(typeof document !== 'undefined' ? document.body : null)
isBodyLocked.value = true

const readerData = useReaderData({ onLoaded: () => initReaderView() })
const { detail, loading, loadingVariant, source, sourceId, scopeId, backToDetail, lastRead } =
  readerData

const readerPaging = useReaderPaging({ detail, scopeId, settings, currentPage, currentGroupIndex })
// prettier-ignore
const {
  scopedPages, total, chapterLabel, chapterShortLabel, nextChapter, prevChapter,
  atChapterEnd, atChapterStart, showEndCard, orderedGroups, isVertical,
  rtlHorizontal, prevIcon, nextIcon, toLocalPage, currentGroupLabel,
  lastGroupIndex, atLastGroup, atFinalPage,
} = readerPaging

const readerChrome = useReaderChrome({ settingsOpen, filmstripOpen, pipOpen })
const { chromeVisible, showChromeTemporarily } = readerChrome

// prettier-ignore
const readerNavigation = useReaderNavigation({
  scrollEl, settings, currentPage, currentGroupIndex,
  pageGroups: readerPaging.pageGroups, lastGroupIndex: readerPaging.lastGroupIndex,
  clampToScope: readerPaging.clampToScope, groupIndexForPage: readerPaging.groupIndexForPage,
  groupFirstPage: readerPaging.groupFirstPage, showChromeTemporarily,
  resetAutoTurnCountdown: () => readerAutoTurn.resetAutoTurnCountdown(),
  source, sourceId, nextChapter, prevChapter, scopeId, router,
})
const { progressValue, pillActive, isSwitchingChapter } = readerNavigation

// prettier-ignore
const readerAutoTurn = useAutoTurn({
  settings, currentGroupIndex, lastGroupIndex: readerPaging.lastGroupIndex,
  hasNextChapter: computed(() => Boolean(nextChapter.value)),
  settingsOpen, filmstripOpen, pipOpen, pipBlocked,
  canAdvanceInPip: computed(() => total.value > 0 && !atFinalPage.value), chromeVisible,
  onAdvance: () => advanceAutoTurn(), onScheduleChromeHide: readerChrome.scheduleChromeHide,
})
const { isAutoTurnActive, autoTurnRemaining, autoTurnPaused, toggleAutoTurnPause } = readerAutoTurn

// prettier-ignore
const {
  initReaderView, advanceAutoTurn, onPageReady, onViewportWheel,
  onViewportTouchStart, onViewportTouchEnd, onUserInteract,
  onContainerScroll, onReaderClick, onSelectChapter, toggleFullscreen,
  prevGroup, nextGroup, goToPage, goNextChapter, goPrevChapter,
  isZoomed, zoomedPage, resetZoom, getPageZoomStyle, onPageDblClick,
  onPagePointerDown, onPagePointerMove, onPagePointerUp, onPagePointerCancel,
  onPageLostPointerCapture, isPipSupported, pipMountTarget, pipEndOpen,
  togglePip, closePip, canPipPrev, canPipNext, pipPrevPage, pipNextPage, pipRestartComic,
  onPipDrawerChange, syncPipPage, openPipEnd,
} = useReaderInteraction({
  userInteracted, currentPage, currentGroupIndex, settingsOpen, filmstripOpen, toggleFilmstrip,
  pipOpen, pipBlocked, reducedMotion,
  route, router, settings: readerSettings, bubble: readerBubble, data: readerData,
  paging: readerPaging, chrome: readerChrome, navigation: readerNavigation, autoTurn: readerAutoTurn,
})

const {
  recommendations,
  libraryItems,
  isDirectPass,
  onReaderCompleted,
  onSelectComic,
  onOpenComicDetail,
  onBackToShelf,
} = useReaderCompletion({ source, sourceId, detail, total, lastRead })

const { recordSession, deactivateSession } = useReadingSession()

watch(
  [source, sourceId, currentPage, () => detail.value?.meta.page_count],
  ([s, sid, p, fullPages]) => {
    if (s && sid && p > 0) {
      recordSession({
        source: s,
        sourceId: sid,
        page: p,
        totalPages: fullPages ?? 0,
      })
    }
  },
  { immediate: true },
)

onBeforeRouteLeave(() => {
  deactivateSession()
})

onUnmounted(() => {
  isBodyLocked.value = false
})
</script>

<template>
  <div class="reader-view" :data-vertical="isVertical" :data-mode="settings.mode">
    <ReaderTopBar
      :title="detail?.meta.title ?? '载入中…'"
      :display-id="detail?.meta.display_id ?? ''"
      :chapter="chapterLabel"
      :hidden="!chromeVisible"
      :pip-supported="isPipSupported"
      :pip-open="pipOpen"
      @back="backToDetail"
      @open-settings="settingsOpen = true"
      @toggle-fullscreen="toggleFullscreen"
      @toggle-pip="togglePip"
    />

    <div v-if="loading" class="reader-loading">
      <ReaderLoadingState :variant="loadingVariant" text="正在整理书页…" full-frame />
    </div>

    <section v-else-if="pipOpen" class="reader-pip-placeholder" aria-live="polite">
      <div class="reader-pip-card">
        <AppIcon name="picture-in-picture" size="2xl" />
        <p class="reader-pip-heading">正在桌面悬浮阅览窗中阅读</p>
        <p class="reader-pip-sub">
          {{ detail?.meta.title }} · 第 {{ toLocalPage(currentPage) }} / {{ total }} 页
        </p>
        <AppButton theme="reader" variant="primary" size="sm" @click="closePip">
          还原到主窗口
        </AppButton>
      </div>
    </section>

    <ReaderViewport
      v-else
      ref="viewportRef"
      :settings="settings"
      :source="source"
      :source-id="sourceId"
      :scope-id="scopeId"
      :is-switching-chapter="isSwitchingChapter"
      :ordered-groups="orderedGroups"
      :current-group-index="currentGroupIndex"
      :show-end-card="showEndCard"
      :rtl-horizontal="rtlHorizontal"
      :loading-variant="loadingVariant"
      :to-local-page="toLocalPage"
      :recommendations="recommendations"
      :target-bubble="targetBubble"
      :next-chapter="nextChapter"
      :chapter-short-label="chapterShortLabel"
      :is-zoomed="isZoomed"
      :zoomed-page="zoomedPage"
      :get-page-zoom-style="getPageZoomStyle"
      @scroll="onContainerScroll"
      @wheel="onViewportWheel"
      @touch-start="onViewportTouchStart"
      @touch-end="onViewportTouchEnd"
      @user-interact="onUserInteract"
      @page-ready="onPageReady"
      @mousemove="showChromeTemporarily"
      @reader-click="onReaderClick"
      @page-dbl-click="onPageDblClick"
      @page-pointer-down="onPagePointerDown"
      @page-pointer-move="onPagePointerMove"
      @page-pointer-up="onPagePointerUp"
      @page-pointer-cancel="onPagePointerCancel"
      @page-lost-pointer-capture="onPageLostPointerCapture"
      @next-chapter="goNextChapter"
      @back-to-detail="backToDetail"
      @back-to-shelf="onBackToShelf"
      @select-comic="onSelectComic"
      @open-comic-detail="onOpenComicDetail"
      @completed="onReaderCompleted"
    />

    <ReaderProgress :progress="progressValue" :invert="rtlHorizontal" />

    <ReaderChapterBanners
      v-if="!loading && !isZoomed && !pipOpen"
      :prev-chapter="prevChapter"
      :next-chapter="nextChapter"
      :at-chapter-start="atChapterStart"
      :at-chapter-end="atChapterEnd"
      :chapter-short-label="chapterShortLabel"
      :mode="settings.mode"
      :disabled="isSwitchingChapter"
      @prev-chapter="goPrevChapter"
      @next-chapter="goNextChapter"
    />

    <ReaderHud
      v-if="!loading && !pipOpen"
      :auto-turn="isAutoTurnActive"
      :at-last-group="atLastGroup && !nextChapter"
      :auto-turn-paused="autoTurnPaused"
      :settings-open="settingsOpen"
      :auto-turn-remaining="autoTurnRemaining"
      :current-group-label="currentGroupLabel"
      :total="total"
      :prev-icon="prevIcon"
      :next-icon="nextIcon"
      :can-prev="
        currentGroupIndex > 0 || (settings.mode !== 'vertical-continuous' && Boolean(prevChapter))
      "
      :can-next="
        currentGroupIndex < lastGroupIndex ||
        (settings.mode !== 'vertical-continuous' && Boolean(nextChapter))
      "
      :hidden="!chromeVisible && !isAutoTurnActive"
      :filmstrip-open="filmstripOpen"
      @toggle-auto-turn-pause="toggleAutoTurnPause"
      @toggle-filmstrip="toggleFilmstrip()"
      @prev="prevGroup"
      @next="nextGroup"
    />

    <ReaderFilmstrip
      v-if="!loading && !pipOpen"
      :open="filmstripOpen"
      :source="source"
      :source-id="sourceId"
      :ordered-groups="orderedGroups"
      :current-group-index="currentGroupIndex"
      :current-page="currentPage"
      :total="total"
      :mode="settings.mode"
      :pages-per-view="settings.pagesPerView"
      :rtl-horizontal="rtlHorizontal"
      :chapters="detail?.meta.chapters"
      :current-chapter-id="scopeId"
      :to-local-page="toLocalPage"
      @select-page="goToPage"
      @select-chapter="onSelectChapter"
      @close="filmstripOpen = false"
    />

    <ReaderFloatingPill
      v-if="!loading && settings.mode === 'vertical-continuous' && settings.seamless"
      :current="toLocalPage(currentPage)"
      :total="total"
      :active="pillActive"
      :suppressed="chromeVisible || settingsOpen || filmstripOpen || isZoomed || pipOpen"
    />

    <ReaderPipWindow
      v-if="pipOpen"
      :open="pipOpen"
      :mount-target="pipMountTarget"
      :loading="loading"
      :end-open="pipEndOpen"
      :at-final-page="atFinalPage"
      :title="detail?.meta.title ?? ''"
      :chapter-label="chapterLabel"
      :chapters="detail?.meta.chapters"
      :current-chapter-id="scopeId"
      :current-source="source"
      :current-source-id="sourceId"
      :page-src="pageFileUrl(source, sourceId, currentPage)"
      :current-page="currentPage"
      :current-local-page="toLocalPage(currentPage)"
      :total="total"
      :scoped-pages="scopedPages"
      :to-local-page="toLocalPage"
      :can-prev="canPipPrev"
      :can-next="canPipNext"
      :rtl-horizontal="rtlHorizontal"
      :reader-mode="settings.mode"
      :fit="settings.fit"
      :seamless="settings.seamless"
      :reduced-motion="reducedMotion"
      :next-chapter="nextChapter"
      :loading-variant="loadingVariant"
      :auto-turn-active="isAutoTurnActive"
      :auto-turn-paused="autoTurnPaused"
      :auto-turn-remaining="autoTurnRemaining"
      :settings-open="settingsOpen"
      :recommendations="recommendations"
      :library-items="libraryItems"
      :is-direct-pass="isDirectPass"
      @prev="pipPrevPage"
      @next="pipNextPage"
      @close="closePip"
      @completed="onReaderCompleted"
      @restart="pipRestartComic"
      @select-comic="onSelectComic"
      @select-chapter="onSelectChapter"
      @toggle-auto-turn-pause="toggleAutoTurnPause"
      @drawer-change="onPipDrawerChange"
      @sync-page="syncPipPage"
      @open-end="openPipEnd"
    />

    <!-- 放大态悬浮还原胶囊 -->
    <Transition name="zoom-pill">
      <div v-if="isZoomed" class="reader-zoom-reset-bar">
        <AppButton
          theme="reader"
          variant="primary"
          size="sm"
          icon="refresh"
          class="reader-zoom-reset-btn"
          title="还原画页原始比例 (Esc 或双击任意处)"
          @click="resetZoom"
        >
          <span>还原视图</span>
        </AppButton>
      </div>
    </Transition>

    <ReaderSettingsPanel :open="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>

<style scoped>
.reader-view {
  --reader-chrome-h: clamp(4.4rem, 8dvh, 6.2rem);
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
  background: var(--reader-bg);
  padding: var(--space-4);
}

.reader-pip-placeholder {
  display: grid;
  place-items: center;
  height: 100dvh;
  background: var(--reader-bg);
  padding: var(--space-5);
}

.reader-pip-card {
  display: grid;
  justify-items: center;
  gap: var(--space-3);
  max-width: 24rem;
  padding: var(--space-6) var(--space-5);
  text-align: center;
  color: var(--reader-ink);
  background: var(--reader-surface);
  border: 1px solid var(--reader-line);
  border-radius: var(--radius-3);
}

.reader-pip-heading {
  margin: 0;
  font-size: var(--text-md);
  font-weight: 600;
}

.reader-pip-sub {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted);
}

.reader-zoom-reset-bar {
  position: absolute;
  left: 50%;
  bottom: max(var(--space-6), env(safe-area-inset-bottom, 0px));
  translate: -50% 0;
  z-index: 25;
  pointer-events: auto;
}

.reader-zoom-reset-btn {
  box-shadow:
    0 4px 16px rgb(0 0 0 / 60%),
    0 0 0 1px var(--reader-line);
}

.zoom-pill-enter-active,
.zoom-pill-leave-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    translate var(--duration-2) var(--ease-out);
}

.zoom-pill-enter-from,
.zoom-pill-leave-to {
  opacity: 0;
  translate: -50% var(--space-2);
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

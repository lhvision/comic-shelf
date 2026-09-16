<script setup lang="ts">
/**
 * @file ReaderView.vue
 * @description 沉浸式阅读器主视图（纯编排视图，脚本严格 ≤150 行）。
 *
 * 遵循 docs/agents/frontend.md 规范：
 * - 视图轻量化（View Thinness ≤150 行）；
 * - 状态机分层下沉至 composables；
 * - 契约自解释与顶层精准解构。
 */

import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePreferredReducedMotion, useToggle } from '@vueuse/core'
import { useReaderSettings } from '@/composables/useReaderSettings'
import { useReaderPaging } from '@/composables/useReaderPaging'
import { useReaderChrome } from '@/composables/useReaderChrome'
import { useAutoTurn } from '@/composables/useAutoTurn'
import { useReaderNavigation } from '@/composables/useReaderNavigation'
import { useReaderData } from '@/composables/useReaderData'
import { useReaderBubble } from '@/composables/useReaderBubble'
import { useReaderCompletion } from '@/composables/useReaderCompletion'
import { useReaderInteraction } from '@/composables/useReaderInteraction'
import ReaderTopBar from '@/components/reader/ReaderTopBar.vue'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'
import ReaderViewport from '@/components/reader/ReaderViewport.vue'
import ReaderProgress from '@/components/reader/ReaderProgress.vue'
import ReaderChapterBanners from '@/components/reader/ReaderChapterBanners.vue'
import ReaderHud from '@/components/reader/ReaderHud.vue'
import ReaderFloatingPill from '@/components/reader/ReaderFloatingPill.vue'
import ReaderSettingsPanel from '@/components/reader/ReaderSettingsPanel.vue'

const route = useRoute()
const router = useRouter()
const readerSettings = useReaderSettings()
const { settings } = readerSettings

const readerBubble = useReaderBubble(route, router)
const { targetBubble } = readerBubble
const currentPage = ref(1)
const currentGroupIndex = ref(0)
const [settingsOpen] = useToggle(false)
const reducedMotion = usePreferredReducedMotion()

const viewportRef = ref<{ scrollEl: HTMLElement | null } | null>(null)
const scrollEl = computed(() => viewportRef.value?.scrollEl ?? null)
const userInteracted = ref(false)

const readerData = useReaderData({ onLoaded: () => initReaderView() })
const { detail, loading, loadingVariant, source, sourceId, scopeId, backToDetail, lastRead } =
  readerData

const readerPaging = useReaderPaging({
  detail,
  scopeId,
  settings,
  currentPage,
  currentGroupIndex,
})
const {
  total,
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
  prevIcon,
  nextIcon,
  toLocalPage,
  currentGroupLabel,
  lastGroupIndex,
  atLastGroup,
} = readerPaging

const readerChrome = useReaderChrome({ settingsOpen })
const { chromeVisible, showChromeTemporarily } = readerChrome

const readerNavigation = useReaderNavigation({
  scrollEl,
  settings,
  currentPage,
  currentGroupIndex,
  pageGroups: readerPaging.pageGroups,
  lastGroupIndex: readerPaging.lastGroupIndex,
  clampToScope: readerPaging.clampToScope,
  groupIndexForPage: readerPaging.groupIndexForPage,
  groupFirstPage: readerPaging.groupFirstPage,
  showChromeTemporarily,
  resetAutoTurnCountdown: () => readerAutoTurn.resetAutoTurnCountdown(),
  source,
  sourceId,
  nextChapter,
  prevChapter,
  scopeId,
  router,
})
const { progressValue, pillActive, prevGroup, nextGroup, goNextChapter, goPrevChapter } =
  readerNavigation

const isAutoTurnActive = computed(
  () => settings.autoTurn && settings.mode !== 'vertical-continuous',
)

const readerAutoTurn = useAutoTurn({
  settings,
  currentGroupIndex,
  lastGroupIndex: readerPaging.lastGroupIndex,
  settingsOpen,
  chromeVisible,
  onAdvance: () => advanceAutoTurn(),
  onScheduleChromeHide: readerChrome.scheduleChromeHide,
})
const { autoTurnRemaining, autoTurnPaused, toggleAutoTurnPause } = readerAutoTurn

const {
  initReaderView,
  advanceAutoTurn,
  onPageReady,
  onViewportWheel,
  onUserInteract,
  onContainerScroll,
  onReaderClick,
  toggleFullscreen,
} = useReaderInteraction({
  userInteracted,
  currentPage,
  currentGroupIndex,
  settingsOpen,
  reducedMotion: computed(() => Boolean(reducedMotion.value)),
  route,
  settings: readerSettings,
  bubble: readerBubble,
  data: readerData,
  paging: readerPaging,
  chrome: readerChrome,
  navigation: readerNavigation,
  autoTurn: readerAutoTurn,
})

const { recommendations, onReaderCompleted, onSelectComic, onOpenComicDetail, onBackToShelf } =
  useReaderCompletion({ source, sourceId, detail, total, lastRead })
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
      :current-group-index="currentGroupIndex"
      :show-end-card="showEndCard"
      :rtl-horizontal="rtlHorizontal"
      :loading-variant="loadingVariant"
      :to-local-page="toLocalPage"
      :recommendations="recommendations"
      :target-bubble="targetBubble"
      :next-chapter="nextChapter"
      :chapter-short-label="chapterShortLabel"
      @scroll="onContainerScroll"
      @wheel="onViewportWheel"
      @user-interact="onUserInteract"
      @page-ready="onPageReady"
      @mousemove="showChromeTemporarily"
      @reader-click="onReaderClick"
      @next-chapter="goNextChapter"
      @back-to-detail="backToDetail"
      @back-to-shelf="onBackToShelf"
      @select-comic="onSelectComic"
      @open-comic-detail="onOpenComicDetail"
      @completed="onReaderCompleted"
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
      :auto-turn="isAutoTurnActive"
      :at-last-group="atLastGroup"
      :auto-turn-paused="autoTurnPaused"
      :settings-open="settingsOpen"
      :auto-turn-remaining="autoTurnRemaining"
      :current-group-label="currentGroupLabel"
      :total="total"
      :prev-icon="prevIcon"
      :next-icon="nextIcon"
      :can-prev="currentGroupIndex > 0"
      :can-next="currentGroupIndex < lastGroupIndex"
      :hidden="!chromeVisible && !isAutoTurnActive"
      @toggle-auto-turn-pause="toggleAutoTurnPause"
      @prev="prevGroup"
      @next="nextGroup"
    />

    <ReaderFloatingPill
      v-if="!loading && settings.mode === 'vertical-continuous' && settings.seamless"
      :current="toLocalPage(currentPage)"
      :total="total"
      :active="pillActive"
      :suppressed="chromeVisible || settingsOpen"
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
  background: var(--reader-bg);
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

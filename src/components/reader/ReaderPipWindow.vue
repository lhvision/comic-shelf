<script setup lang="ts">
/**
 * ReaderPipWindow.vue — 桌面悬浮阅览窗（Document Picture-in-Picture）内容外壳。
 * 通过 Vue `<Teleport>` 挂载到独立置顶 PiP 窗口，负责顶底栏、热键分发、单页自适应切换与状态调度，
 * 并静态组合连续长卷（ReaderPipContinuousStage）与选话换书抽屉（ReaderPipSwitcherPanel）。
 */
import { computed, ref, useTemplateRef, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ComicPageImage from '@/components/ComicPageImage.vue'
import ReaderPipBookItem from '@/components/reader/pip/ReaderPipBookItem.vue'
import ReaderPipContinuousStage from '@/components/reader/pip/ReaderPipContinuousStage.vue'
import ReaderPipSwitcherPanel from '@/components/reader/pip/ReaderPipSwitcherPanel.vue'
import type { FitMode, ReaderMode } from '@/composables/useReaderSettings'
import type { Chapter, LibrarySummary } from '@/types'

const props = withDefaults(
  defineProps<{
    open: boolean
    mountTarget: HTMLElement | null
    loading?: boolean
    endOpen?: boolean
    atFinalPage?: boolean
    title: string
    chapterLabel?: string
    chapters?: Chapter[]
    currentChapterId?: string | null
    currentSource?: string
    currentSourceId?: string
    pageSrc: string
    currentPage?: number
    currentLocalPage: number
    total: number
    scopedPages?: number[]
    toLocalPage?: (page: number) => number
    canPrev: boolean
    canNext: boolean
    rtlHorizontal: boolean
    readerMode?: ReaderMode
    fit?: FitMode
    seamless?: boolean
    reducedMotion?: boolean
    nextChapter?: Chapter | null
    loadingVariant?: string | number
    autoTurnActive?: boolean
    autoTurnPaused?: boolean
    autoTurnRemaining?: number
    settingsOpen?: boolean
    recommendations?: LibrarySummary[]
    libraryItems?: LibrarySummary[]
    isDirectPass?: boolean
  }>(),
  {
    loading: false,
    endOpen: false,
    atFinalPage: false,
    chapterLabel: '',
    chapters: () => [],
    currentChapterId: null,
    currentSource: '',
    currentSourceId: '',
    currentPage: 0,
    scopedPages: () => [],
    toLocalPage: undefined,
    readerMode: 'vertical-paged',
    fit: 'height',
    seamless: false,
    reducedMotion: false,
    nextChapter: null,
    loadingVariant: undefined,
    autoTurnActive: false,
    autoTurnPaused: false,
    autoTurnRemaining: 0,
    settingsOpen: false,
    recommendations: () => [],
    libraryItems: () => [],
    isDirectPass: false,
  },
)

const emit = defineEmits<{
  prev: []
  next: []
  close: []
  completed: []
  restart: []
  selectComic: [source: string, sourceId: string]
  selectChapter: [chapterId: string]
  toggleAutoTurnPause: []
  drawerChange: [open: boolean]
  syncPage: [page: number]
  openEnd: []
}>()

const pipKeyTarget = computed(
  () => props.mountTarget?.ownerDocument.defaultView ?? props.mountTarget?.ownerDocument ?? null,
)
const drawerMode = ref<'chapters' | 'books' | null>(null)
const continuousStageRef =
  useTemplateRef<InstanceType<typeof ReaderPipContinuousStage>>('continuousStageRef')

const hasChapters = computed(() => props.chapters.length > 1)
const canSwitchBooks = computed(() => !props.isDirectPass && props.libraryItems.length > 0)
const visibleRecommendations = computed(() =>
  props.isDirectPass ? [] : props.recommendations.slice(0, 3),
)
const isContinuousStrip = computed(
  () =>
    props.readerMode === 'vertical-continuous' &&
    (props.seamless || props.fit === 'width') &&
    props.scopedPages.length > 0 &&
    Boolean(props.currentSource && props.currentSourceId),
)
const showAutoTurnControl = computed(
  () => props.autoTurnActive && !props.atFinalPage && !props.endOpen && !isContinuousStrip.value,
)
const autoTurnBlocked = computed(
  () => props.autoTurnPaused || props.settingsOpen || Boolean(drawerMode.value),
)
const autoTurnAriaLabel = computed(() => {
  if (props.settingsOpen || drawerMode.value) return '自动切换倒计时，面板展开中已暂停'
  if (props.autoTurnPaused) return '自动切换已暂停，点击继续'
  if (props.autoTurnRemaining <= 1) return '即将切换，点击暂停'
  return `${props.autoTurnRemaining} 秒后切换，点击暂停`
})

const transitionDir = ref<'forward' | 'backward' | 'none'>('none')

watch(
  () =>
    [
      props.currentLocalPage,
      props.currentChapterId,
      `${props.currentSource}/${props.currentSourceId}`,
      props.endOpen,
    ] as const,
  ([page, chap, comic, end], [prevPage, prevChap, prevComic, prevEnd]) => {
    if (
      props.reducedMotion ||
      isContinuousStrip.value ||
      comic !== prevComic ||
      chap !== prevChap ||
      end !== prevEnd ||
      end ||
      prevEnd
    ) {
      transitionDir.value = 'none'
      return
    }
    if (page > prevPage) {
      transitionDir.value = 'forward'
    } else if (page < prevPage) {
      transitionDir.value = 'backward'
    } else {
      transitionDir.value = 'none'
    }
  },
  { flush: 'sync' },
)

const transitionName = computed(() => {
  if (props.reducedMotion || transitionDir.value === 'none') return 'pip-slide-none'
  if (props.readerMode === 'horizontal') {
    const moveLeft = props.rtlHorizontal
      ? transitionDir.value === 'backward'
      : transitionDir.value === 'forward'
    return moveLeft ? 'pip-slide-left' : 'pip-slide-right'
  }
  return transitionDir.value === 'forward' ? 'pip-slide-up' : 'pip-slide-down'
})

watch(drawerMode, (mode) => {
  emit('drawerChange', Boolean(mode))
})

function toggleDrawer(mode: 'chapters' | 'books') {
  drawerMode.value = drawerMode.value === mode ? null : mode
}

function pickChapter(chapterId: string) {
  drawerMode.value = null
  emit('selectChapter', chapterId)
}

function pickComic(source: string, sourceId: string) {
  drawerMode.value = null
  emit('selectComic', source, sourceId)
}

watch(
  [() => `${props.currentSource}/${props.currentSourceId}`, () => props.open],
  ([comic, isOpen], [prevComic]) => {
    if (comic !== prevComic || !isOpen) {
      drawerMode.value = null
    }
  },
)

watch(
  () => props.isDirectPass,
  (direct) => {
    if (direct && drawerMode.value === 'books') {
      drawerMode.value = null
    }
  },
)

watch(
  () => props.endOpen,
  (isEnd, wasEnd) => {
    if (isEnd && !wasEnd) {
      drawerMode.value = null
      emit('completed')
    }
  },
)

function handleLeftTap() {
  if (props.rtlHorizontal) {
    if (props.canNext) emit('next')
  } else if (props.canPrev) {
    emit('prev')
  }
}

function handleRightTap() {
  if (props.rtlHorizontal) {
    if (props.canPrev) emit('prev')
  } else if (props.canNext) {
    emit('next')
  }
}

useEventListener(pipKeyTarget, 'keydown', (event: KeyboardEvent) => {
  if (!props.open) return
  if (event.ctrlKey || event.metaKey || event.altKey) return
  const target = event.target as Partial<Element> | null
  const inInput =
    typeof target?.closest === 'function' &&
    Boolean(target.closest('input, textarea, select, [contenteditable]'))

  if (event.key === 'Escape') {
    event.preventDefault()
    if (drawerMode.value) {
      drawerMode.value = null
    } else {
      emit('close')
    }
    return
  }

  if (inInput || drawerMode.value || props.loading) return

  if (isContinuousStrip.value && !props.endOpen) {
    const stage = continuousStageRef.value
    if (!stage) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      stage.scrollByStep('line-down')
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      stage.scrollByStep('line-up')
      return
    }
    if (event.key === 'PageDown' || event.key === ' ') {
      event.preventDefault()
      stage.scrollByStep(event.key === ' ' && event.shiftKey ? 'page-up' : 'page-down')
      return
    }
    if (event.key === 'PageUp') {
      event.preventDefault()
      stage.scrollByStep('page-up')
    }
    return
  }

  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    handleLeftTap()
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    handleRightTap()
    return
  }
  if (event.key === 'ArrowDown' || event.key === 'PageDown' || event.key === ' ') {
    event.preventDefault()
    if (props.canNext) emit('next')
    return
  }
  if (event.key === 'ArrowUp' || event.key === 'PageUp') {
    event.preventDefault()
    if (props.canPrev) emit('prev')
  }
})
</script>

<template>
  <Teleport v-if="open && mountTarget" :to="mountTarget">
    <div class="pip-reader" :data-rtl="rtlHorizontal ? 'true' : undefined">
      <header class="pip-reader-header">
        <div class="pip-reader-meta">
          <strong class="pip-reader-title" :title="title">{{ title }}</strong>
          <button
            v-if="chapterLabel && hasChapters"
            type="button"
            class="pip-reader-chapter is-clickable"
            :aria-expanded="drawerMode === 'chapters'"
            :title="`切换章节：${chapterLabel}`"
            @click="toggleDrawer('chapters')"
          >
            {{ chapterLabel }}
          </button>
          <span v-else-if="chapterLabel" class="pip-reader-chapter">{{ chapterLabel }}</span>
        </div>

        <div class="pip-reader-actions">
          <AppButton
            v-if="hasChapters"
            theme="reader"
            :variant="drawerMode === 'chapters' ? 'soft' : 'ghost'"
            size="xs"
            :aria-expanded="drawerMode === 'chapters'"
            title="选择本话章节"
            @click="toggleDrawer('chapters')"
          >
            <span>选话</span>
          </AppButton>
          <AppButton
            v-if="canSwitchBooks"
            theme="reader"
            :variant="drawerMode === 'books' ? 'soft' : 'ghost'"
            size="xs"
            icon="book-open"
            :aria-expanded="drawerMode === 'books'"
            title="快捷切换书库作品"
            @click="toggleDrawer('books')"
          >
            <span>换书</span>
          </AppButton>
          <AppButton
            theme="reader"
            variant="ghost"
            size="xs"
            icon="external-link"
            title="还原到主阅读器窗口"
            @click="$emit('close')"
          >
            <span>还原</span>
          </AppButton>
        </div>
      </header>

      <main class="pip-reader-stage">
        <ReaderPipSwitcherPanel
          v-if="drawerMode"
          :mode="drawerMode"
          :chapters="chapters"
          :current-chapter-id="currentChapterId"
          :current-source="currentSource"
          :current-source-id="currentSourceId"
          :library-items="libraryItems"
          :has-chapters="hasChapters"
          :can-switch-books="canSwitchBooks"
          @switch-mode="(mode) => (drawerMode = mode)"
          @close="drawerMode = null"
          @select-chapter="pickChapter"
          @select-comic="pickComic"
        />

        <div v-else-if="loading" class="pip-status-card">
          <p class="pip-status-title">正在翻开书卷…</p>
          <p class="pip-status-sub">{{ title }}</p>
        </div>

        <section v-else-if="endOpen" class="pip-end-view" aria-label="本子翻完了与接卷推荐">
          <div class="pip-end-head">
            <span class="pip-end-seal">〔 全卷完 · 归阁 〕</span>
            <h2 class="pip-end-title">本子翻完了</h2>
            <p class="pip-end-sub">
              {{
                visibleRecommendations.length > 0
                  ? '接下来想在小窗继续翻哪一本？'
                  : '合上书卷，墨香犹在。'
              }}
            </p>
          </div>

          <div v-if="visibleRecommendations.length > 0" class="pip-rec-list">
            <ReaderPipBookItem
              v-for="item in visibleRecommendations"
              :key="`${item.source}/${item.source_id}`"
              :item="item"
              show-author
              @select="pickComic"
            />
          </div>

          <div class="pip-end-actions">
            <AppButton
              theme="reader"
              variant="soft"
              size="xs"
              icon="refresh"
              @click="$emit('restart')"
            >
              <span>再看一遍</span>
            </AppButton>
            <AppButton
              v-if="canSwitchBooks"
              theme="reader"
              variant="ghost"
              size="xs"
              icon="book-open"
              @click="toggleDrawer('books')"
            >
              <span>去书架挑书</span>
            </AppButton>
          </div>
        </section>

        <ReaderPipContinuousStage
          v-else-if="isContinuousStrip"
          ref="continuousStageRef"
          :current-source="currentSource"
          :current-source-id="currentSourceId"
          :current-chapter-id="currentChapterId"
          :current-page="currentPage"
          :current-local-page="currentLocalPage"
          :scoped-pages="scopedPages"
          :to-local-page="toLocalPage"
          :seamless="seamless"
          :reduced-motion="reducedMotion"
          :next-chapter="nextChapter"
          :loading-variant="loadingVariant"
          @sync-page="(page) => $emit('syncPage', page)"
          @select-chapter="pickChapter"
          @open-end="$emit('openEnd')"
        />

        <div v-else class="pip-page-stage">
          <Transition :name="transitionName">
            <div
              :key="`${currentSource}/${currentSourceId}/${currentChapterId ?? 'all'}/${currentLocalPage}`"
              class="pip-page-slide"
            >
              <ComicPageImage
                :src="pageSrc"
                :alt="`第 ${currentLocalPage} 页`"
                eager
                :loading-variant="loadingVariant"
              />
            </div>
          </Transition>
          <button
            type="button"
            class="pip-tap-zone is-left"
            :aria-label="rtlHorizontal ? '下一页' : '上一页'"
            :disabled="rtlHorizontal ? !canNext : !canPrev"
            @click="handleLeftTap"
          />
          <button
            type="button"
            class="pip-tap-zone is-right"
            :aria-label="rtlHorizontal ? '上一页' : '下一页'"
            :disabled="rtlHorizontal ? !canPrev : !canNext"
            @click="handleRightTap"
          />
        </div>
      </main>

      <footer class="pip-reader-footer">
        <AppButton
          theme="reader"
          variant="ghost"
          size="xs"
          icon="arrow-left"
          :disabled="rtlHorizontal ? !canNext : !canPrev"
          :aria-label="
            rtlHorizontal ? (atFinalPage ? '完读接卷' : '下一页') : endOpen ? '返回末页' : '上一页'
          "
          @click="rtlHorizontal ? $emit('next') : $emit('prev')"
        >
          <span>{{
            rtlHorizontal ? (atFinalPage ? '完读' : '下一页') : endOpen ? '末页' : '上一页'
          }}</span>
        </AppButton>
        <div class="pip-footer-center">
          <span class="pip-reader-counter">
            {{ endOpen ? '全卷完' : `${currentLocalPage} / ${total}` }}
          </span>
          <button
            v-if="showAutoTurnControl"
            type="button"
            class="pip-auto-turn-pill"
            :data-paused="autoTurnBlocked"
            :aria-label="autoTurnAriaLabel"
            :title="autoTurnAriaLabel"
            @click="$emit('toggleAutoTurnPause')"
          >
            <AppIcon v-if="autoTurnBlocked" :name="autoTurnPaused ? 'play' : 'pause'" size="xs" />
            <span v-else class="pip-auto-turn-sec">{{ autoTurnRemaining }}s</span>
          </button>
        </div>
        <AppButton
          theme="reader"
          variant="ghost"
          size="xs"
          icon="arrow-right"
          icon-position="right"
          :disabled="rtlHorizontal ? !canPrev : !canNext"
          :aria-label="
            rtlHorizontal ? (endOpen ? '返回末页' : '上一页') : atFinalPage ? '完读接卷' : '下一页'
          "
          @click="rtlHorizontal ? $emit('prev') : $emit('next')"
        >
          <span>{{
            rtlHorizontal ? (endOpen ? '末页' : '上一页') : atFinalPage ? '完读' : '下一页'
          }}</span>
        </AppButton>
      </footer>
    </div>
  </Teleport>
</template>

<style scoped>
.pip-reader {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  width: 100%;
  height: 100dvh;
  background: var(--reader-bg, #0d0e0c);
  color: var(--reader-ink, #eee7da);
  overflow: hidden;
  -webkit-user-select: none;
  user-select: none;
}

.pip-reader-header,
.pip-reader-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-1-5, 0.375rem) var(--space-2-5, 0.625rem);
  background: color-mix(in oklab, var(--reader-bg, #0d0e0c) 88%, transparent);
}

.pip-reader-header {
  border-bottom: 1px solid var(--reader-line-soft, rgb(238 231 218 / 10%));
}

.pip-reader-footer {
  border-top: 1px solid var(--reader-line-soft, rgb(238 231 218 / 10%));
}

.pip-reader-meta {
  min-width: 0;
  display: grid;
  justify-items: start;
}

.pip-reader-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1, 0.25rem);
  flex-shrink: 0;
}

.pip-reader-title {
  max-width: 100%;
  font-size: var(--text-xs, 0.75rem);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-reader-chapter {
  max-width: 100%;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-reader-chapter.is-clickable {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.pip-reader-chapter.is-clickable:hover {
  color: var(--reader-accent, #e87a58);
}

.pip-reader-stage {
  position: relative;
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  place-items: center;
  padding: var(--space-1, 0.25rem);
  background: var(--reader-page-bg, #11120f);
  overflow: clip;
}

.pip-page-stage {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: clip;
}

.pip-page-slide {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  place-items: center;
}

.pip-page-slide :deep(.comic-page-image) {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.pip-page-slide :deep(.comic-page-image[data-state='loading']) {
  min-height: 0;
  aspect-ratio: auto;
}

.pip-page-slide :deep(.comic-page-img-frame) {
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pip-page-slide :deep(.comic-page-img) {
  max-width: 100%;
  max-height: 100%;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

@media (prefers-reduced-motion: no-preference) {
  .pip-slide-left-enter-active,
  .pip-slide-left-leave-active,
  .pip-slide-right-enter-active,
  .pip-slide-right-leave-active,
  .pip-slide-up-enter-active,
  .pip-slide-up-leave-active,
  .pip-slide-down-enter-active,
  .pip-slide-down-leave-active {
    position: absolute;
    inset: 0;
    transition:
      transform var(--duration-2, 200ms) var(--ease-out, cubic-bezier(0.22, 1, 0.36, 1)),
      opacity var(--duration-2, 200ms) var(--ease-out, cubic-bezier(0.22, 1, 0.36, 1));
  }

  .pip-slide-left-enter-from {
    opacity: 0.4;
    transform: translate3d(100%, 0, 0);
  }
  .pip-slide-left-leave-to {
    opacity: 0.4;
    transform: translate3d(-100%, 0, 0);
  }

  .pip-slide-right-enter-from {
    opacity: 0.4;
    transform: translate3d(-100%, 0, 0);
  }
  .pip-slide-right-leave-to {
    opacity: 0.4;
    transform: translate3d(100%, 0, 0);
  }

  .pip-slide-up-enter-from {
    opacity: 0.4;
    transform: translate3d(0, 100%, 0);
  }
  .pip-slide-up-leave-to {
    opacity: 0.4;
    transform: translate3d(0, -100%, 0);
  }

  .pip-slide-down-enter-from {
    opacity: 0.4;
    transform: translate3d(0, -100%, 0);
  }
  .pip-slide-down-leave-to {
    opacity: 0.4;
    transform: translate3d(0, 100%, 0);
  }
}

.pip-tap-zone {
  position: absolute;
  inset: 0 auto 0 0;
  width: 34%;
  z-index: 2;
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
}

.pip-tap-zone.is-right {
  inset: 0 0 0 auto;
}

.pip-tap-zone:disabled {
  cursor: default;
}

.pip-footer-center {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5, 0.375rem);
}

.pip-reader-counter {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-xs, 0.75rem);
  color: var(--reader-muted, #938d80);
  letter-spacing: 0.04em;
}

.pip-auto-turn-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2rem;
  height: 1.375rem;
  padding: 0 var(--space-1-5, 0.375rem);
  border-radius: var(--radius-pill, 9999px);
  border: 1px solid var(--reader-line, rgb(238 231 218 / 14%));
  background: var(--reader-surface-strong, rgb(238 231 218 / 8%));
  color: var(--reader-accent, #e87a58);
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  cursor: pointer;
}

.pip-auto-turn-pill[data-paused='true'] {
  color: var(--reader-muted, #938d80);
}

.pip-auto-turn-pill:hover {
  border-color: var(--reader-accent, #e87a58);
}

.pip-status-card,
.pip-end-view {
  width: 100%;
  max-width: 24rem;
  display: grid;
  gap: var(--space-3, 0.75rem);
  padding: var(--space-4, 1rem);
  text-align: center;
}

.pip-status-title,
.pip-end-title {
  margin: 0;
  font-size: var(--text-md, 1rem);
  font-weight: 600;
}

.pip-status-sub,
.pip-end-sub {
  margin: 0;
  font-size: var(--text-xs, 0.75rem);
  color: var(--reader-muted, #938d80);
}

.pip-end-seal {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-accent, #e87a58);
  letter-spacing: 0.08em;
}

.pip-end-head {
  display: grid;
  gap: var(--space-1, 0.25rem);
}

.pip-rec-list {
  display: grid;
  gap: var(--space-2, 0.5rem);
  text-align: left;
}

.pip-end-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-2, 0.5rem);
  flex-wrap: wrap;
}

@media (display-mode: picture-in-picture) {
  .pip-reader-stage {
    padding: 0;
  }
}
</style>

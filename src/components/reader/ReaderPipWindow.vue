<script setup lang="ts">
/**
 * ReaderPipWindow.vue — 桌面悬浮阅览窗（Document Picture-in-Picture）内容组件。
 * 通过 Vue `<Teleport>` 挂载到独立置顶 PiP 窗口，支持单页同步翻页与模式一致切换动画、
 * 条漫/宽适配连续滚动长卷、离散模式自动切换倒计时与暂停控制、
 * 多章节直选跳话、末页完读接卷推荐与顶栏快捷换书闭环。
 */
import { computed, nextTick, onScopeDispose, ref, useTemplateRef, watch } from 'vue'
import { useEventListener, useTimeoutFn } from '@vueuse/core'
import { coverSrcset, pageFileUrl } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ComicPageImage from '@/components/ComicPageImage.vue'
import { useReaderHydration, type OrderedGroup } from '@/composables/useReaderHydration'
import type { FitMode, ReaderMode } from '@/composables/useReaderSettings'
import type { Chapter, LibrarySummary } from '@/types'
import { isCompletedComic, isInProgressComic } from '@/utils/is'
import { binarySearchNearestIndex } from '@/utils/math'

const MAX_SWITCHER_ITEMS = 30

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
const searchQuery = ref('')
const searchInputEl = useTemplateRef<HTMLInputElement>('searchInputEl')

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

const continuousScrollEl = useTemplateRef<HTMLElement>('continuousScrollEl')
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
  comicKey: computed(() => `${props.currentSource}/${props.currentSourceId}`),
})

function formatLocalPage(page: number): number {
  return props.toLocalPage ? props.toLocalPage(page) : page
}

let continuousRafId: number | null = null
let isInternalScrollSync = false
let isProgrammaticContinuousScroll = false

const { start: startContinuousScrollUnlock, stop: stopContinuousScrollUnlock } = useTimeoutFn(
  () => {
    isProgrammaticContinuousScroll = false
  },
  380,
  { immediate: false },
)

function unlockContinuousScroll() {
  isProgrammaticContinuousScroll = false
  stopContinuousScrollUnlock()
}

function scrollContinuousToPage(page: number, behavior: ScrollBehavior = 'instant') {
  const el = continuousScrollEl.value
  if (!el) return
  const target = el.querySelector<HTMLElement>(`[data-pip-page="${page}"]`)
  if (!target) return
  if (behavior === 'smooth') {
    isProgrammaticContinuousScroll = true
    stopContinuousScrollUnlock()
    startContinuousScrollUnlock()
    if ('onscrollend' in window) {
      el.addEventListener('scrollend', unlockContinuousScroll, { once: true })
    }
  }
  el.scrollTo({ top: target.offsetTop, left: 0, behavior })
}

function onContinuousScroll() {
  if (isProgrammaticContinuousScroll || continuousRafId !== null) return
  continuousRafId = requestAnimationFrame(() => {
    continuousRafId = null
    if (isProgrammaticContinuousScroll) return
    const el = continuousScrollEl.value
    if (!el || !isContinuousStrip.value || props.scopedPages.length === 0) return

    const pos = el.scrollTop
    const max = el.scrollHeight - el.clientHeight
    let matched = props.scopedPages[0]!

    if (max > 0 && pos >= max - 16) {
      matched = props.scopedPages[props.scopedPages.length - 1]!
    } else if (pos <= 16) {
      matched = props.scopedPages[0]!
    } else {
      const matchedIdx = binarySearchNearestIndex(
        props.scopedPages.length,
        Math.max(0, props.scopedPages.indexOf(props.currentPage)),
        (mid) => {
          const pageNum = props.scopedPages[mid]!
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
        },
      )
      matched = props.scopedPages[matchedIdx] ?? matched
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
  [
    isContinuousStrip,
    () => props.open,
    () => props.endOpen,
    () => Boolean(drawerMode.value),
    () => props.currentChapterId,
    () => props.currentPage,
  ],
  ([continuous, isOpen, isEnd, hasDrawer, chap, page], prevValues) => {
    if (!continuous || !isOpen || isEnd || hasDrawer || page <= 0) return
    if (isInternalScrollSync) return
    const [prevContinuous, prevOpen, prevEnd, prevHasDrawer, prevChap] = prevValues ?? []
    const shouldInstant =
      !prevContinuous || !prevOpen || prevEnd || prevHasDrawer || chap !== prevChap
    void nextTick(() => {
      scrollContinuousToPage(page, shouldInstant || props.reducedMotion ? 'instant' : 'smooth')
    })
  },
  { flush: 'post', immediate: true },
)

onScopeDispose(() => {
  if (continuousRafId !== null) {
    cancelAnimationFrame(continuousRafId)
    continuousRafId = null
  }
  emit('drawerChange', false)
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

const quickSwitchBooks = computed<LibrarySummary[]>(() => {
  if (!canSwitchBooks.value) return []
  const query = searchQuery.value.trim().toLocaleLowerCase()
  const filtered = props.libraryItems.filter((item) => {
    if (item.source === props.currentSource && item.source_id === props.currentSourceId) {
      return false
    }
    if (!query) return true
    const haystack = [item.title, item.display_id, ...(item.authors ?? [])]
      .join('\n')
      .toLocaleLowerCase()
    return haystack.includes(query)
  })

  const statusRank = (item: LibrarySummary) => {
    if (isInProgressComic(item)) return 0
    if (!isCompletedComic(item)) return 1
    return 2
  }

  return filtered
    .toSorted((a, b) => {
      const rankDiff = statusRank(a) - statusRank(b)
      if (rankDiff !== 0) return rankDiff
      const timeA = a.imported_at ? Date.parse(a.imported_at) || 0 : 0
      const timeB = b.imported_at ? Date.parse(b.imported_at) || 0 : 0
      return timeB - timeA
    })
    .slice(0, MAX_SWITCHER_ITEMS)
})

function formatBookStatus(item: LibrarySummary): string {
  if (isCompletedComic(item)) return '已读完'
  if (isInProgressComic(item)) return `在读 ${item.last_page}/${item.page_count}P`
  return '未读'
}

function formatBookMeta(item: LibrarySummary, showAuthor: boolean): string {
  const status = formatBookStatus(item)
  return showAuthor
    ? `${status} · ${item.authors.join(' / ') || '佚名'}`
    : `${item.display_id} · ${status}`
}

function bookCoverSrcset(cover?: string): string | undefined {
  if (!cover) return undefined
  return coverSrcset(cover) || undefined
}

function openDrawer(mode: 'chapters' | 'books') {
  drawerMode.value = mode
  if (mode === 'books') {
    void nextTick(() => {
      searchInputEl.value?.focus()
    })
  }
}

function toggleDrawer(mode: 'chapters' | 'books') {
  if (drawerMode.value === mode) {
    drawerMode.value = null
    return
  }
  openDrawer(mode)
}

function pickChapter(chapterId: string) {
  drawerMode.value = null
  emit('selectChapter', chapterId)
}

function pickComic(source: string, sourceId: string) {
  drawerMode.value = null
  searchQuery.value = ''
  emit('selectComic', source, sourceId)
}

watch(
  () => `${props.currentSource}/${props.currentSourceId}`,
  () => {
    drawerMode.value = null
    searchQuery.value = ''
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
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      drawerMode.value = null
      searchQuery.value = ''
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
        <section
          v-if="drawerMode"
          class="pip-switcher-panel"
          :aria-label="drawerMode === 'chapters' ? '本话章节目录' : '快捷切换藏书'"
        >
          <div class="pip-switcher-tabs">
            <div class="pip-switcher-tab-group">
              <button
                v-if="hasChapters"
                type="button"
                class="pip-tab-btn"
                :class="{ 'is-active': drawerMode === 'chapters' }"
                @click="openDrawer('chapters')"
              >
                本话目录 ({{ chapters.length }})
              </button>
              <button
                v-if="canSwitchBooks"
                type="button"
                class="pip-tab-btn"
                :class="{ 'is-active': drawerMode === 'books' }"
                @click="openDrawer('books')"
              >
                快捷换书
              </button>
            </div>
            <AppButton
              theme="reader"
              variant="ghost"
              size="xs"
              shape="circle"
              icon="close"
              aria-label="关闭切换面板"
              @click="drawerMode = null"
            />
          </div>

          <div v-if="drawerMode === 'chapters'" class="pip-switcher-list">
            <button
              v-for="ch in chapters"
              :key="ch.id"
              type="button"
              class="pip-chapter-item"
              :class="{ 'is-current': ch.id === currentChapterId }"
              @click="pickChapter(ch.id)"
            >
              <span class="pip-chapter-name">第 {{ ch.index }} 話 · {{ ch.title }}</span>
              <span class="pip-chapter-meta">
                {{ ch.id === currentChapterId ? '在看 · ' : '' }}{{ ch.page_count }}P
              </span>
            </button>
          </div>

          <div v-else class="pip-books-body">
            <label class="pip-search-box">
              <AppIcon name="search" size="xs" />
              <input
                ref="searchInputEl"
                v-model="searchQuery"
                type="search"
                class="pip-search-input"
                placeholder="搜标题 / 车号 / 作者…"
                aria-label="搜索书库藏书"
              />
            </label>

            <div class="pip-switcher-list">
              <button
                v-for="item in quickSwitchBooks"
                :key="`${item.source}/${item.source_id}`"
                type="button"
                class="pip-book-item"
                @click="pickComic(item.source, item.source_id)"
              >
                <img
                  v-if="item.cover_paths?.[0]"
                  :src="item.cover_paths[0]"
                  :srcset="bookCoverSrcset(item.cover_paths[0])"
                  sizes="120px"
                  :alt="item.title"
                  class="pip-book-cover"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="pip-book-cover is-empty">{{ item.display_id }}</div>
                <div class="pip-book-info">
                  <strong class="pip-book-title">{{ item.title }}</strong>
                  <span class="pip-book-meta">{{ formatBookMeta(item, false) }}</span>
                </div>
              </button>
              <p v-if="quickSwitchBooks.length === 0" class="pip-empty-hint">未找到匹配的藏书</p>
            </div>
          </div>
        </section>

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
            <button
              v-for="item in visibleRecommendations"
              :key="`${item.source}/${item.source_id}`"
              type="button"
              class="pip-book-item"
              @click="pickComic(item.source, item.source_id)"
            >
              <img
                v-if="item.cover_paths?.[0]"
                :src="item.cover_paths[0]"
                :srcset="bookCoverSrcset(item.cover_paths[0])"
                sizes="120px"
                :alt="item.title"
                class="pip-book-cover"
                loading="lazy"
                decoding="async"
              />
              <div v-else class="pip-book-cover is-empty">{{ item.display_id }}</div>
              <div class="pip-book-info">
                <strong class="pip-book-title">{{ item.title }}</strong>
                <span class="pip-book-meta">{{ formatBookMeta(item, true) }}</span>
              </div>
            </button>
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

        <div
          v-else-if="isContinuousStrip"
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
                @click="pickChapter(nextChapter.id)"
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

.pip-continuous-scroll {
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

.pip-continuous-end-title {
  margin: 0;
  font-size: var(--text-xs, 0.75rem);
  color: var(--reader-ink, #eee7da);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.pip-switcher-panel {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--space-2, 0.5rem);
  padding: var(--space-2, 0.5rem);
  box-sizing: border-box;
}

.pip-switcher-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2, 0.5rem);
}

.pip-switcher-tab-group {
  display: flex;
  gap: var(--space-1, 0.25rem);
}

.pip-tab-btn {
  padding: var(--space-1, 0.25rem) var(--space-2-5, 0.625rem);
  border-radius: var(--radius-pill, 9999px);
  border: 1px solid var(--reader-line, rgb(238 231 218 / 14%));
  background: transparent;
  color: var(--reader-muted, #938d80);
  font-size: var(--text-xs, 0.75rem);
  cursor: pointer;
}

.pip-tab-btn.is-active {
  background: var(--reader-surface-strong, rgb(238 231 218 / 8%));
  color: var(--reader-ink, #eee7da);
  border-color: var(--reader-accent, #e87a58);
}

.pip-books-body {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--space-2, 0.5rem);
}

.pip-search-box {
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-1-5, 0.375rem) var(--space-2-5, 0.625rem);
  border-radius: var(--radius-2, 0.625rem);
  background: var(--reader-surface, rgb(238 231 218 / 4%));
  border: 1px solid var(--reader-line, rgb(238 231 218 / 14%));
  color: var(--reader-muted, #938d80);
}

.pip-search-input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--reader-ink, #eee7da);
  font-size: var(--text-xs, 0.75rem);
}

.pip-switcher-list {
  min-height: 0;
  overflow-y: auto;
  display: grid;
  align-content: start;
  gap: var(--space-1-5, 0.375rem);
  scrollbar-width: thin;
}

.pip-chapter-item,
.pip-book-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2-5, 0.625rem);
  padding: var(--space-2, 0.5rem);
  border-radius: var(--radius-2, 0.625rem);
  border: 1px solid var(--reader-line-soft, rgb(238 231 218 / 10%));
  background: var(--reader-surface, rgb(238 231 218 / 4%));
  color: var(--reader-ink, #eee7da);
  text-align: left;
  cursor: pointer;
}

.pip-chapter-item:hover,
.pip-book-item:hover {
  background: var(--reader-surface-hover, rgb(238 231 218 / 14%));
}

.pip-chapter-item.is-current {
  border-color: var(--reader-accent, #e87a58);
}

.pip-chapter-name {
  min-width: 0;
  font-size: var(--text-xs, 0.75rem);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-chapter-meta {
  flex-shrink: 0;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
}

.pip-book-item {
  justify-content: flex-start;
}

.pip-book-cover {
  width: 2.25rem;
  height: 3rem;
  object-fit: cover;
  border-radius: var(--radius-1, 0.375rem);
  flex-shrink: 0;
  background: var(--reader-bg, #0d0e0c);
}

.pip-book-cover.is-empty {
  display: grid;
  place-items: center;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
}

.pip-book-info {
  min-width: 0;
  display: grid;
  gap: var(--space-0-5, 0.125rem);
}

.pip-book-title {
  font-size: var(--text-xs, 0.75rem);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-book-meta,
.pip-empty-hint {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-empty-hint {
  margin: var(--space-4, 1rem) 0;
  text-align: center;
}

@media (display-mode: picture-in-picture) {
  .pip-reader-stage {
    padding: 0;
  }
}
</style>

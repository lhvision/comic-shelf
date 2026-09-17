<script setup lang="ts">
/**
 * @file ReaderFilmstrip.vue
 * @description 阅读器胶片预览轨组件（Filmstrip Scrubber / Reader Filmstrip）。
 *
 * 核心职责：
 * 1. 胶片卷轴抽屉（Filmstrip Drawer）：
 *    - 以半透明磨砂浮层（Overlay Scrim）覆盖在阅读器底边，主画卷视口 0 重排、0 颠簸；
 * 2. 章节专注轨与自适应跨度（Adaptive Scope）：
 *    - 单章节漫画一轨到底；多章节作品自动锁定当前话并提供跨话快速切换；
 * 3. 视窗注水与物理宽高比共享：
 *    - 实例化 useReaderHydration 并设定 bufferOverride 为 ±8，仅加载本地 WebP 缩略图；
 *    - 共享 useComicRatioPool 宽高比池，未就绪单元格由极简静默纸印骨架（quiescent-paper）撑高；
 * 4. 组级光标框（Group-level Framing Cursor）：
 *    - 针对 1/2/4 页分屏，单页微缩独立平铺，通过朱砂金色高亮外框整体圈定当前分屏组；
 * 5. RTL 镜像流向（RTL Inverted Filmstrip Flow）：
 *    - 横向日漫模式下严格遵循 dir="rtl"，滑动方向与阅读流向 100% 吻合；
 * 6. 零胶水悬停画中画（ReaderHoverPreview 集成）：
 *    - 鼠标悬停单元格时防抖浮现单页画中画气泡。
 */

import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'
import { useDebounceFn, useTimeoutFn } from '@vueuse/core'
import { pageThumbUrl } from '@/api/client'
import { useReaderHydration, type OrderedGroup } from '@/composables/useReaderHydration'
import { useComicRatioPool } from '@/composables/useComicRatioPool'
import type { Chapter } from '@/types'
import type { ReaderMode } from '@/composables/useReaderSettings'
import AppIcon from '@/components/AppIcon.vue'
import ReaderHoverPreview from '@/components/reader/ReaderHoverPreview.vue'
import { clamp } from '@/utils/math'

const props = withDefaults(
  defineProps<{
    /** 抽屉展开状态 */
    open: boolean
    /** 漫画来源标识 */
    source: string
    /** 漫画编号标识 */
    sourceId: string
    /** 全局分屏分组列表 */
    orderedGroups: OrderedGroup[]
    /** 当前激活的分屏分组全局索引 */
    currentGroupIndex: number
    /** 当前全局页码 */
    currentPage: number
    /** 全书总页数 */
    total: number
    /** 阅读模式 */
    mode: ReaderMode
    /** 每屏页数 */
    pagesPerView: number
    /** 是否横向日漫右翻模式 */
    rtlHorizontal: boolean
    /** 漫画所有章节列表（多章节作品） */
    chapters?: Chapter[]
    /** 当前阅读的章节标识 */
    currentChapterId?: string | null
    /** 章节相对页码转换函数 */
    toLocalPage?: (p: number) => number
  }>(),
  {
    chapters: () => [],
    currentChapterId: undefined,
    toLocalPage: undefined,
  },
)

const emit = defineEmits<{
  selectGroup: [groupIndex: number]
  selectPage: [page: number]
  selectChapter: [chapterId: string]
  close: []
}>()

const comicKey = computed(() => `${props.source}/${props.sourceId}`)
const railEl = useTemplateRef<HTMLElement>('railEl')
const containerEl = useTemplateRef<HTMLElement>('containerEl')

// 1. 漫画会话级宽高比池
const { getPageRatio, setPageRatio } = useComicRatioPool(comicKey)

// 2. 章节切片与作用域自适应
const currentChapter = computed<Chapter | null>(() => {
  if (!props.chapters || props.chapters.length === 0 || !props.currentChapterId) {
    return null
  }
  return props.chapters.find((c) => c.id === props.currentChapterId) ?? null
})

const currentChapterIndex = computed<number>(() => {
  if (!currentChapter.value || !props.chapters) return -1
  return props.chapters.findIndex((c) => c.id === currentChapter.value?.id)
})

const prevChapter = computed<Chapter | null>(() => {
  if (currentChapterIndex.value <= 0 || !props.chapters) return null
  return props.chapters[currentChapterIndex.value - 1] ?? null
})

const nextChapter = computed<Chapter | null>(() => {
  if (currentChapterIndex.value < 0 || !props.chapters) return null
  if (currentChapterIndex.value >= props.chapters.length - 1) return null
  return props.chapters[currentChapterIndex.value + 1] ?? null
})

/** 局限于当前章节或全本的分组切片 */
const scopedGroups = computed<OrderedGroup[]>(() => {
  const chap = currentChapter.value
  if (!chap) {
    return props.orderedGroups
  }
  const start = chap.start
  const end = chap.start + chap.page_count
  return props.orderedGroups.filter((g) => g.pages.some((p) => p >= start && p < end))
})

const scopedCurrentGroupIndex = computed<number>(() => {
  const curGroup = props.orderedGroups[props.currentGroupIndex]
  if (!curGroup) return 0
  const idx = scopedGroups.value.findIndex((g) => g.index === curGroup.index)
  return idx >= 0 ? idx : 0
})

// 3. 胶片轨注水视窗：始终死死锚定当前实际阅读页，保证阅读上下文 100% 同步
const { isGroupHydrated, getPageStyle } = useReaderHydration({
  orderedGroups: scopedGroups,
  currentGroupIndex: scopedCurrentGroupIndex,
  comicKey,
  bufferOverride: { forward: 12, backward: 12 },
})

// 4. 视口滚动居中锚定（精确物理像素居中，杜绝 scrollIntoView 在 absolute 抽屉中的失效偏差）
let isClickNavigating = false
const { start: startClickNavTimer, stop: stopClickNavTimer } = useTimeoutFn(
  () => {
    isClickNavigating = false
  },
  500,
  { immediate: false },
)

function lockClickNavigation() {
  isClickNavigating = true
  stopClickNavTimer()
  startClickNavTimer()
}

function centerTileByGroupIndex(groupIndex: number, smooth = true) {
  nextTick(() => {
    const rail = railEl.value
    if (!rail) return
    const targetEl = rail.querySelector<HTMLElement>(`[data-group-index="${groupIndex}"]`)
    if (!targetEl) return

    const railRect = rail.getBoundingClientRect()
    const targetRect = targetEl.getBoundingClientRect()
    const hasGeometry = railRect.width > 0 && targetRect.width > 0
    const delta = hasGeometry
      ? targetRect.left + targetRect.width / 2 - (railRect.left + railRect.width / 2)
      : targetEl.offsetLeft - rail.clientWidth / 2 + targetEl.clientWidth / 2

    if (typeof rail.scrollBy === 'function' && hasGeometry) {
      if (Math.abs(delta) > 1) {
        rail.scrollBy({
          left: delta,
          behavior: smooth ? 'smooth' : 'auto',
        })
      }
    } else if (typeof rail.scrollTo === 'function') {
      const targetLeft = props.rtlHorizontal
        ? rail.scrollLeft + delta
        : Math.max(0, rail.scrollLeft + delta)
      rail.scrollTo({
        left: targetLeft,
        behavior: smooth ? 'smooth' : 'auto',
      })
    } else {
      rail.scrollLeft += delta
    }
  })
}

function centerActiveTile(smooth = true) {
  nextTick(() => {
    const rail = railEl.value
    if (!rail) return
    const activeEl = rail.querySelector<HTMLElement>('[data-group-active="true"]')
    if (!activeEl) return

    const railRect = rail.getBoundingClientRect()
    const targetRect = activeEl.getBoundingClientRect()
    const hasGeometry = railRect.width > 0 && targetRect.width > 0
    const delta = hasGeometry
      ? targetRect.left + targetRect.width / 2 - (railRect.left + railRect.width / 2)
      : activeEl.offsetLeft - rail.clientWidth / 2 + activeEl.clientWidth / 2

    if (typeof rail.scrollBy === 'function' && hasGeometry) {
      if (Math.abs(delta) > 1) {
        rail.scrollBy({
          left: delta,
          behavior: smooth ? 'smooth' : 'auto',
        })
      }
    } else if (typeof rail.scrollTo === 'function') {
      const targetLeft = props.rtlHorizontal
        ? rail.scrollLeft + delta
        : Math.max(0, rail.scrollLeft + delta)
      rail.scrollTo({
        left: targetLeft,
        behavior: smooth ? 'smooth' : 'auto',
      })
    } else {
      rail.scrollLeft += delta
    }
  })
}

const debouncedCenterActiveTile = useDebounceFn((smooth: boolean) => {
  centerActiveTile(smooth)
}, 80)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      centerActiveTile(false)
    }
  },
)

watch(
  () => props.currentGroupIndex,
  () => {
    if (props.open && !isClickNavigating) {
      debouncedCenterActiveTile(true)
    }
  },
)

// 5. 画中画悬停气泡联动与防抖（120ms）
const hoverState = ref<{
  show: boolean
  page: number
  anchorX: number
  groupTip?: string
}>({
  show: false,
  page: 0,
  anchorX: 0,
  groupTip: undefined,
})

const { start: scheduleHideHover, stop: cancelHideHover } = useTimeoutFn(
  () => {
    hoverState.value.show = false
  },
  100,
  { immediate: false },
)

function onTileHover(e: MouseEvent, page: number, group: OrderedGroup) {
  cancelHideHover()
  const container = containerEl.value
  if (!container) return
  const containerRect = container.getBoundingClientRect()
  const tileRect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const centerX = tileRect.left + tileRect.width / 2 - containerRect.left

  // 边界钳位：保证画中画中心不超出胶片轨左右 80px 边缘
  const clampedX = clamp(centerX, 80, containerRect.width - 80)

  let tip: string | undefined
  if (props.pagesPerView > 1 && group.pages.length > 1) {
    tip = `第 ${group.index + 1} 屏 · [${group.pages.map((p) => (props.toLocalPage ? props.toLocalPage(p) : p)).join('-')}]`
  }

  hoverState.value = {
    show: true,
    page,
    anchorX: clampedX,
    groupTip: tip,
  }
}

function onTileLeave() {
  scheduleHideHover()
}

function onContextMenu() {
  cancelHideHover()
  hoverState.value.show = false
}

let isDraggingRail = false
let dragStartX = 0
let dragScrollLeft = 0
let hasDragged = false
let activePointerId: number | null = null

function onRailPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  // 触控端放行浏览器原生硬件加速平滑动量滚动，仅桌面鼠标接管拖拽漫游
  if (e.pointerType === 'touch') return
  const rail = railEl.value
  if (!rail) return
  isDraggingRail = true
  hasDragged = false
  dragStartX = e.clientX
  dragScrollLeft = rail.scrollLeft
  activePointerId = e.pointerId
  // 核心避坑：绝对不能在 pointerdown 时抢先调用 rail.setPointerCapture(e.pointerId)！
  // 现代浏览器在容器提前 capture 后，会将随后的原生 click 事件截胡重定向给 rail 容器，
  // 导致子元素 .filmstrip-tile 无法接收到原生 click 事件。
}

function onRailPointerMove(e: PointerEvent) {
  if (!isDraggingRail) return
  const rail = railEl.value
  if (!rail) return
  const diff = e.clientX - dragStartX
  if (!hasDragged && Math.abs(diff) > 5) {
    hasDragged = true
    // 仅在判定为真实位移拖拽后，才按需接管 Pointer Capture 确保平稳跟手
    if (activePointerId !== null && !rail.hasPointerCapture(activePointerId)) {
      try {
        rail.setPointerCapture(activePointerId)
      } catch {
        // Defensive: ignore InvalidPointerId if gesture ended abruptly
      }
    }
  }
  if (hasDragged) {
    const factor = props.rtlHorizontal ? 1 : -1
    rail.scrollLeft = dragScrollLeft + diff * factor
  }
}

const { start: startDragResetTimer } = useTimeoutFn(
  () => {
    hasDragged = false
  },
  120,
  { immediate: false },
)

function onRailPointerUp() {
  if (!isDraggingRail) return
  isDraggingRail = false
  const rail = railEl.value
  if (rail && activePointerId !== null && rail.hasPointerCapture(activePointerId)) {
    try {
      rail.releasePointerCapture(activePointerId)
    } catch {
      // Ignored
    }
  }
  activePointerId = null
  if (hasDragged) {
    startDragResetTimer()
  }
}

function onRailWheel(e: WheelEvent) {
  const rail = railEl.value
  if (!rail) return
  const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY
  const factor = props.rtlHorizontal ? -1 : 1
  rail.scrollLeft += delta * factor
}

function handleTileClick(group: OrderedGroup, page: number) {
  if (hasDragged) return
  cancelHideHover()
  hoverState.value.show = false
  lockClickNavigation()
  centerTileByGroupIndex(group.index, true)
  emit('selectGroup', group.index)
  emit('selectPage', page)
}

function handleThumbLoad(page: number, e: Event) {
  const img = e.target as HTMLImageElement
  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    setPageRatio(page, `${img.naturalWidth} / ${img.naturalHeight}`)
  }
}
</script>

<template>
  <Transition name="filmstrip-fade">
    <div v-if="open" class="filmstrip-backdrop" aria-hidden="true" @click="emit('close')" />
  </Transition>

  <Transition name="filmstrip-drawer">
    <div
      v-if="open"
      ref="containerEl"
      class="reader-filmstrip"
      :data-mode="mode"
      :data-pages="pagesPerView"
      role="region"
      aria-label="分卷缩略胶卷"
      @contextmenu="onContextMenu"
    >
      <!-- 画中画悬停气泡 -->
      <ReaderHoverPreview
        :show="hoverState.show"
        :page="hoverState.page"
        :source="source"
        :source-id="sourceId"
        :anchor-x="hoverState.anchorX"
        :ratio="getPageRatio(hoverState.page)"
        :to-local-page="toLocalPage"
        :group-tip="hoverState.groupTip"
        @image-ready="(page, ratio) => setPageRatio(page, ratio)"
      />

      <!-- 顶栏元信息与控制 -->
      <header class="filmstrip-header">
        <div class="filmstrip-meta">
          <span class="filmstrip-label">胶片画卷</span>
          <span v-if="currentChapter" class="filmstrip-chapter-title">
            {{ currentChapter.title || `第 ${currentChapter.index + 1} 话` }}
          </span>
          <span class="filmstrip-counter">
            {{ toLocalPage ? toLocalPage(currentPage) : currentPage }} / {{ total }}
          </span>
        </div>

        <div class="filmstrip-actions">
          <button
            v-if="prevChapter"
            type="button"
            class="filmstrip-chap-btn"
            aria-label="上一话胶卷"
            @click="emit('selectChapter', prevChapter.id)"
          >
            <AppIcon name="arrow-left" size="xs" />
            <span>上一话</span>
          </button>
          <button
            v-if="nextChapter"
            type="button"
            class="filmstrip-chap-btn"
            aria-label="下一话胶卷"
            @click="emit('selectChapter', nextChapter.id)"
          >
            <span>下一话</span>
            <AppIcon name="arrow-right" size="xs" />
          </button>
          <button
            type="button"
            class="filmstrip-close-btn"
            aria-label="收起胶片轨"
            @click="emit('close')"
          >
            <AppIcon name="close" size="xs" />
          </button>
        </div>
      </header>

      <!-- 核心胶片横向滚动轨 -->
      <nav
        ref="railEl"
        class="filmstrip-rail"
        :dir="rtlHorizontal ? 'rtl' : 'ltr'"
        tabindex="0"
        aria-label="微缩胶片列表"
        @wheel.prevent.stop="onRailWheel"
        @pointerdown="onRailPointerDown"
        @pointermove="onRailPointerMove"
        @pointerup="onRailPointerUp"
        @pointercancel="onRailPointerUp"
        @contextmenu="onContextMenu"
      >
        <section
          v-for="(group, gIdx) in scopedGroups"
          :key="group.index"
          class="filmstrip-group"
          :data-group-index="group.index"
          :data-group-active="group.index === currentGroupIndex"
          :class="{ 'group-active': group.index === currentGroupIndex }"
        >
          <article
            v-for="page in group.pages"
            :key="page"
            class="filmstrip-tile"
            :data-page="page"
            :data-page-active="page === currentPage"
            :style="getPageStyle(page)"
            role="button"
            tabindex="0"
            :aria-label="`第 ${toLocalPage ? toLocalPage(page) : page} 页`"
            :aria-current="page === currentPage ? 'page' : undefined"
            @mouseenter="onTileHover($event, page, group)"
            @mouseleave="onTileLeave"
            @click="handleTileClick(group, page)"
            @keydown.enter.prevent="handleTileClick(group, page)"
            @keydown.space.prevent="handleTileClick(group, page)"
          >
            <img
              v-if="isGroupHydrated(gIdx)"
              :src="pageThumbUrl(source, sourceId, page)"
              :alt="`第 ${toLocalPage ? toLocalPage(page) : page} 页缩略图`"
              class="tile-thumb"
              draggable="false"
              loading="lazy"
              decoding="async"
              @load="handleThumbLoad(page, $event)"
            />
            <div v-else class="tile-quiescent-paper" aria-hidden="true">
              <span class="quiescent-page-mark">
                {{ toLocalPage ? toLocalPage(page) : page }}
              </span>
            </div>

            <span class="tile-badge" aria-hidden="true">
              {{ toLocalPage ? toLocalPage(page) : page }}
            </span>
          </article>
        </section>
      </nav>
    </div>
  </Transition>
</template>

<style scoped>
.filmstrip-backdrop {
  position: fixed;
  inset: 0;
  z-index: calc(var(--z-dropdown, 35) - 1);
  background: var(--reader-scrim-soft);
  backdrop-filter: blur(2px);
  cursor: pointer;
}

.reader-filmstrip {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: var(--z-dropdown, 35);
  display: flex;
  flex-direction: column;
  background: var(--reader-scrim-strong);
  backdrop-filter: blur(20px);
  border-top: 1px solid var(--reader-line-strong);
  box-shadow: 0 -12px 36px var(--reader-backdrop);
  user-select: none;
  touch-action: pan-x;
}

.filmstrip-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-1-5) max(var(--space-4), env(safe-area-inset-right)) var(--space-1)
    max(var(--space-4), env(safe-area-inset-left));
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-ink);
  border-bottom: 1px solid var(--reader-line-soft);
}

.filmstrip-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.filmstrip-label {
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--accent);
}

.filmstrip-chapter-title {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--reader-text);
}

.filmstrip-counter {
  color: var(--reader-muted);
}

.filmstrip-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
}

.filmstrip-chap-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: var(--control-sm);
  padding: 0 var(--space-2);
  border-radius: var(--radius-sm);
  border: 1px solid var(--reader-line);
  background: var(--reader-surface);
  color: var(--reader-ink);
  font-size: 0.6875rem;
  cursor: pointer;
  transition: background var(--duration-1) var(--ease-out);
}

.filmstrip-chap-btn:hover {
  background: var(--reader-surface-hover);
}

.filmstrip-close-btn {
  width: var(--control-sm);
  height: var(--control-sm);
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid var(--reader-line);
  background: var(--reader-surface);
  color: var(--reader-ink);
  cursor: pointer;
  transition: background var(--duration-1) var(--ease-out);
}

.filmstrip-close-btn:hover {
  background: var(--reader-surface-hover);
}

/* 核心滚动轨 */
.filmstrip-rail {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) max(var(--space-4), env(safe-area-inset-right))
    max(var(--space-2), env(safe-area-inset-bottom)) max(var(--space-4), env(safe-area-inset-left));
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--reader-line) transparent;
}

.filmstrip-rail::-webkit-scrollbar {
  height: 4px;
}

.filmstrip-rail::-webkit-scrollbar-thumb {
  background: var(--reader-line-strong);
  border-radius: var(--radius-full);
}

/* 分屏成组与组级光标框 */
.filmstrip-group {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px;
  border-radius: var(--radius-sm);
  border: 2px solid transparent;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
  flex-shrink: 0;
}

/* 组级光标：朱砂金色装订线框 */
.filmstrip-group.group-active {
  border-color: var(--accent);
  background-color: color-mix(in oklab, var(--accent) 12%, transparent);
}

/* 单张胶片单元 */
.filmstrip-tile {
  position: relative;
  width: 52px;
  height: 68px;
  border-radius: var(--radius-xs);
  overflow: hidden;
  background: var(--reader-page-bg);
  box-shadow: 0 2px 6px var(--reader-scrim);
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    transform var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out),
    outline-color var(--duration-1) var(--ease-out);
}

.filmstrip-tile:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--reader-scrim-strong);
}

.filmstrip-tile[data-page-active='true'] {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.filmstrip-tile:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.tile-thumb {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.tile-quiescent-paper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    145deg,
    color-mix(in oklab, var(--reader-page-bg) 90%, var(--reader-ink) 10%),
    var(--reader-page-bg)
  );
}

.quiescent-page-mark {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted);
}

.tile-badge {
  position: absolute;
  right: 2px;
  bottom: 2px;
  padding: 0 3px;
  border-radius: var(--radius-xs);
  background: var(--reader-scrim-strong);
  color: var(--reader-ink);
  font-family: var(--font-mono);
  font-size: 0.625rem;
  line-height: 1.2;
}

.filmstrip-tile[data-page-active='true'] .tile-badge {
  background: var(--accent);
  color: var(--accent-contrast, #fff);
  font-weight: 600;
}

/* 抽屉平滑推展与收起动画 */
.filmstrip-drawer-enter-active,
.filmstrip-drawer-leave-active {
  transition:
    translate var(--duration-2) var(--ease-out),
    opacity var(--duration-2) var(--ease-out);
}

.filmstrip-drawer-enter-from,
.filmstrip-drawer-leave-to {
  translate: 0 100%;
  opacity: 0;
}

@media (hover: none) {
  .filmstrip-tile:hover {
    transform: none;
    box-shadow: 0 2px 6px var(--reader-scrim);
  }
}

@media (max-width: 680px) {
  .filmstrip-tile {
    width: 44px;
    height: 58px;
  }

  .filmstrip-chap-btn {
    min-height: var(--control-md);
    padding: 0 var(--space-2);
  }

  .filmstrip-close-btn {
    width: var(--control-md);
    height: var(--control-md);
  }
}

.filmstrip-fade-enter-active,
.filmstrip-fade-leave-active {
  transition: opacity var(--duration-2) var(--ease-out);
}

.filmstrip-fade-enter-from,
.filmstrip-fade-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .filmstrip-fade-enter-active,
  .filmstrip-fade-leave-active {
    transition: none;
  }

  .filmstrip-drawer-enter-active,
  .filmstrip-drawer-leave-active {
    transition: opacity var(--duration-1) linear;
  }
  .filmstrip-drawer-enter-from,
  .filmstrip-drawer-leave-to {
    translate: 0 0;
  }
}
</style>

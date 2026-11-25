<script setup lang="ts">
import { computed, nextTick, onMounted, onWatcherCleanup, ref, useTemplateRef, watch } from 'vue'
import { useEventListener, useResizeObserver } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import AppPopover from '@/components/AppPopover.vue'
import { prefersReducedMotion } from '@/utils/is'
import { clamp } from '@/utils/math'
import type { Chapter } from '@/types'

const WINDOW_THRESHOLD = 48
const WINDOW_RADIUS = 16
const WINDOW_SIZE = WINDOW_RADIUS * 2 + 1
const JUMP_SEGMENT_SIZE = 100
const JUMP_RENDER_LIMIT = 40

/**
 * 多章节详情页的「章节切换条」 —— 横向 chips，标出章节序数 / 标题 / 页数。
 * 单章节（chapters.length <= 1）时不渲染任何内容，保持旧详情页外观。
 * 纯展示组件：选中态由父级 activeId 驱动，切换以 emit 上抛。
 *
 * - 超长连载窗口裁剪（> 48 话）：仅挂载以当前激活章节为中心的 ±16 话（最多 33 枚 chip），
 *   消除数千节点 DOM 与 O(N²) 查找开销，并在外侧提供原生 Top Layer 快速跳话浮层。
 * - 选中 chip 的横向居中：通过几何差值计算当前激活卡片在容器视口的中心位置。
 *   首屏挂载 / 尺寸变化采用瞬间直达（behavior: 'auto'），用户切话采用平滑平移（减弱动效时退化为 auto）。
 * - 边缘渐隐提示：优先使用纯 CSS `animation-timeline: scroll(self inline)` + `@property` 遮罩，
 *   不支持时回退至首尾哨兵 `IntersectionObserver`，全程零滚动监听重渲染。
 * - 键盘操作：左/右方向键与 Home/End 在全书章节间移动（即使开启窗口裁剪亦可直达首末话）。
 */
const props = withDefaults(
  defineProps<{
    chapters: Chapter[]
    activeId: string | null
    /** 用在上/下一话之间的 pager 模式时去掉全宽通排样式，紧凑嵌入 */
    inPager?: boolean
  }>(),
  { inPager: false },
)

const emit = defineEmits<{ change: [id: string] }>()

const listEl = useTemplateRef<HTMLElement>('listEl')
const startSentinelEl = useTemplateRef<HTMLElement>('startSentinelEl')
const endSentinelEl = useTemplateRef<HTMLElement>('endSentinelEl')
const jumpInputEl = useTemplateRef<HTMLInputElement>('jumpInputEl')
const buttonEls = new Map<string, HTMLElement>()

// 防御：父级必须解构 unwrap 后传入；万一传了 Ref 或 undefined，这里兜底为空数组。
const chapterList = computed(() => (Array.isArray(props.chapters) ? props.chapters : []))
const activeIndex = computed(() => chapterList.value.findIndex((c) => c.id === props.activeId))
const isWindowed = computed(() => chapterList.value.length > WINDOW_THRESHOLD)

const windowRange = computed(() => {
  const len = chapterList.value.length
  if (!isWindowed.value || len === 0) {
    return { start: 0, end: len }
  }
  const center = activeIndex.value >= 0 ? activeIndex.value : 0
  const maxStart = Math.max(0, len - WINDOW_SIZE)
  const start = clamp(center - WINDOW_RADIUS, 0, maxStart)
  const end = Math.min(len, start + WINDOW_SIZE)
  return { start, end }
})

const visibleItems = computed(() => {
  const { start, end } = windowRange.value
  return chapterList.value.slice(start, end).map((chapter, offset) => ({
    chapter,
    idx: start + offset,
  }))
})

const activeOrdinalLabel = computed(() => chapterList.value[activeIndex.value]?.index ?? 1)

const supportsScrollTimeline =
  typeof CSS !== 'undefined' &&
  typeof CSS.supports === 'function' &&
  CSS.supports('animation-timeline', 'scroll()') &&
  CSS.supports('mask', 'linear-gradient(black, black) no-clip subtract')

function setButtonRef(id: string, el: unknown) {
  if (el instanceof HTMLElement) {
    buttonEls.set(id, el)
  } else {
    buttonEls.delete(id)
  }
}

/** 标记是否已完成初次挂载与初始定位 */
let hasMounted = false

/**
 * 将当前激活章节卡片滚动至容器视口物理正中心。
 *
 * @param smooth 是否平滑过渡。首屏与视口尺寸变动时为 false（瞬间直达），用户交互切话时为 true。
 */
function scrollToActive(smooth = false) {
  const container = listEl.value
  const activeKey = props.activeId ?? ''
  const el = buttonEls.get(activeKey)
  if (!el || !container) return
  if (container.scrollWidth <= container.clientWidth) return

  const containerRect = container.getBoundingClientRect()
  const elRect = el.getBoundingClientRect()
  const currentScroll = container.scrollLeft

  // 视口相对位移：当前滚动偏移 + 元素相对容器视口的可视左偏 - 视口居中余量
  const targetLeft = clamp(
    currentScroll +
      (elRect.left - containerRect.left) -
      (container.clientWidth - el.offsetWidth) / 2,
    0,
    container.scrollWidth - container.clientWidth,
  )

  const behavior: ScrollBehavior = smooth && !prefersReducedMotion() ? 'smooth' : 'auto'
  if (typeof container.scrollTo === 'function') {
    container.scrollTo({ left: targetLeft, behavior })
  } else {
    container.scrollLeft = targetLeft
  }
}

onMounted(async () => {
  await nextTick()
  requestAnimationFrame(() => {
    scrollToActive(false)
    hasMounted = true
  })
})

watch(
  () => [props.activeId, chapterList.value.length] as const,
  async ([newId, len], [oldId]) => {
    if (!newId || len === 0) return
    await nextTick()
    requestAnimationFrame(() => {
      const isUserAction = hasMounted && oldId !== undefined && newId !== oldId
      scrollToActive(isUserAction)
    })
  },
)

useResizeObserver(listEl, () => {
  if (hasMounted && activeIndex.value >= 0) {
    scrollToActive(false)
  }
})

// 不支持 CSS scroll-driven fades 时，回退为首尾哨兵 IntersectionObserver，直接切换 dataset 属性避免 Vue 重渲染
if (!supportsScrollTimeline) {
  watch(
    [listEl, startSentinelEl, endSentinelEl],
    ([container, startEl, endEl]) => {
      if (!container || !startEl || !endEl || typeof IntersectionObserver === 'undefined') return

      const observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.target === startEl) {
              container.dataset.scrollLeft = String(!entry.isIntersecting)
            } else if (entry.target === endEl) {
              container.dataset.scrollRight = String(!entry.isIntersecting)
            }
          }
        },
        { root: container, threshold: 0 },
      )
      observer.observe(startEl)
      observer.observe(endEl)
      onWatcherCleanup(() => observer.disconnect())
    },
    { flush: 'post' },
  )
}

useEventListener(listEl, 'keydown', (event: KeyboardEvent) => {
  const idx = activeIndex.value
  let nextId: string | null = null

  if (event.key === 'Home') {
    event.preventDefault()
    nextId = chapterList.value[0]?.id ?? null
  } else if (event.key === 'End') {
    event.preventDefault()
    nextId = chapterList.value[chapterList.value.length - 1]?.id ?? null
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    if (idx < 0) return
    event.preventDefault()
    const delta = event.key === 'ArrowRight' ? 1 : -1
    nextId = chapterList.value[clamp(idx + delta, 0, chapterList.value.length - 1)]?.id ?? null
  }

  if (nextId && nextId !== props.activeId) {
    emit('change', nextId)
    void nextTick(() => buttonEls.get(nextId)?.focus())
  }
})

function chapterLabel(chapter: Chapter) {
  return chapter.title ? `第 ${chapter.index} 話 · ${chapter.title}` : `第 ${chapter.index} 話`
}

/** O(1) 索引态判定：已翻过 / 当前 / 未翻到 */
function stateByIndex(idx: number): 'past' | 'active' | 'upcoming' {
  if (activeIndex.value < 0) return 'upcoming'
  if (idx === activeIndex.value) return 'active'
  return idx < activeIndex.value ? 'past' : 'upcoming'
}

// === 快速跳话浮层（仅在 > 48 话时渲染） ===
const jumpOpen = ref(false)
const jumpQuery = ref('')
const selectedSegment = ref(0)
const segmentExpanded = ref(false)

const jumpSegments = computed(() => {
  const len = chapterList.value.length
  const count = Math.ceil(len / JUMP_SEGMENT_SIZE)
  return Array.from({ length: count }, (_, segIdx) => {
    const startIdx = segIdx * JUMP_SEGMENT_SIZE
    const endIdx = Math.min(len, startIdx + JUMP_SEGMENT_SIZE)
    const firstOrdinal = chapterList.value[startIdx]?.index ?? startIdx + 1
    const lastOrdinal = chapterList.value[endIdx - 1]?.index ?? endIdx
    return {
      segIdx,
      startIdx,
      endIdx,
      label: `${firstOrdinal}–${lastOrdinal}`,
    }
  })
})

const trimmedJumpQuery = computed(() => jumpQuery.value.trim().toLowerCase())

const filteredJump = computed(() => {
  const list = chapterList.value
  const q = trimmedJumpQuery.value
  if (!q) {
    const seg = jumpSegments.value[selectedSegment.value] ?? jumpSegments.value[0]
    if (!seg) return { items: [] as Chapter[], total: 0, isSegmentTruncated: false }
    const slice = list.slice(seg.startIdx, seg.endIdx)
    if (segmentExpanded.value || slice.length <= JUMP_RENDER_LIMIT) {
      return { items: slice, total: slice.length, isSegmentTruncated: false }
    }
    const localActive =
      activeIndex.value >= seg.startIdx && activeIndex.value < seg.endIdx
        ? activeIndex.value - seg.startIdx
        : 0
    const offset =
      localActive >= JUMP_RENDER_LIMIT
        ? Math.min(slice.length - JUMP_RENDER_LIMIT, Math.max(0, localActive - 15))
        : 0
    return {
      items: slice.slice(offset, offset + JUMP_RENDER_LIMIT),
      total: slice.length,
      isSegmentTruncated: true,
    }
  }

  const numericMatch = q.match(/\d+/)?.[0]
  const exactOrdinal =
    numericMatch && /^\d+$/.test(q.replace(/^第|話$|话$/g, '').trim()) ? Number(numericMatch) : null

  const matches: Chapter[] = []
  let exactTarget: Chapter | null = null
  for (const chapter of list) {
    if (exactOrdinal !== null && chapter.index === exactOrdinal) {
      exactTarget = chapter
      continue
    }
    if (String(chapter.index).includes(q) || chapter.title.toLowerCase().includes(q)) {
      matches.push(chapter)
    }
  }
  const ordered = exactTarget ? [exactTarget, ...matches] : matches
  return {
    items: ordered.slice(0, JUMP_RENDER_LIMIT),
    total: ordered.length,
    isSegmentTruncated: false,
  }
})

let pendingSegmentOverride: number | null = null

function openJumpPopover(preferStart = false) {
  pendingSegmentOverride = preferStart ? 0 : null
  jumpOpen.value = true
}

function onJumpOpen() {
  const fallbackSeg = Math.floor(Math.max(0, activeIndex.value) / JUMP_SEGMENT_SIZE)
  selectedSegment.value = pendingSegmentOverride ?? fallbackSeg
  pendingSegmentOverride = null
  segmentExpanded.value = false
  jumpQuery.value = ''
  void nextTick(() => jumpInputEl.value?.focus())
}

function selectSegment(segIdx: number) {
  selectedSegment.value = segIdx
  segmentExpanded.value = false
}

function selectJumpChapter(id: string) {
  jumpOpen.value = false
  if (id !== props.activeId) {
    emit('change', id)
  }
}

function submitJumpQuery() {
  const first = filteredJump.value.items[0]
  if (first) {
    selectJumpChapter(first.id)
  }
}
</script>

<template>
  <div v-if="chapterList.length > 1" class="chapter-switcher-shell" :data-pager="inPager">
    <div ref="listEl" class="chapter-switcher" :data-pager="inPager" role="group" aria-label="章节">
      <span
        v-if="!supportsScrollTimeline"
        ref="startSentinelEl"
        class="scroll-sentinel scroll-sentinel--start"
        aria-hidden="true"
      />

      <button
        v-if="isWindowed && windowRange.start > 0"
        type="button"
        class="chapter-edge-jump"
        :title="`前面还有 ${windowRange.start} 话，点击快速跳话`"
        :aria-label="`前面还有 ${windowRange.start} 话，点击跳话`"
        @click="openJumpPopover(true)"
      >
        <AppIcon name="more" size="xs" />
        <span class="chapter-edge-range">1–{{ windowRange.start }}</span>
      </button>

      <button
        v-for="{ chapter, idx } in visibleItems"
        :key="chapter.id"
        :ref="(el) => setButtonRef(chapter.id, el)"
        type="button"
        class="chapter-chip"
        :aria-pressed="activeId === chapter.id"
        :data-active="activeId === chapter.id"
        :data-state="stateByIndex(idx)"
        :title="chapterLabel(chapter)"
        @click="emit('change', chapter.id)"
      >
        <span class="chapter-ordinal">{{ chapter.index }}</span>
        <span class="chapter-title">{{ chapterLabel(chapter) }}</span>
        <span v-if="activeId === chapter.id" class="chapter-current" aria-hidden="true">当前</span>
        <span class="chapter-count">{{ chapter.page_count }} P</span>
      </button>

      <button
        v-if="isWindowed && windowRange.end < chapterList.length"
        type="button"
        class="chapter-edge-jump"
        :title="`后面还有 ${chapterList.length - windowRange.end} 话，点击快速跳话`"
        :aria-label="`后面还有 ${chapterList.length - windowRange.end} 话，点击跳话`"
        @click="openJumpPopover(false)"
      >
        <AppIcon name="more" size="xs" />
        <span class="chapter-edge-range">{{ windowRange.end + 1 }}–{{ chapterList.length }}</span>
      </button>

      <span
        v-if="!supportsScrollTimeline"
        ref="endSentinelEl"
        class="scroll-sentinel scroll-sentinel--end"
        aria-hidden="true"
      />
    </div>

    <AppPopover
      v-if="isWindowed"
      v-model:open="jumpOpen"
      side="bottom"
      align="end"
      width="min(22rem, calc(100vw - 2rem))"
      aria-label="快速跳话"
      @open="onJumpOpen"
    >
      <template #default="{ open, commandProps }">
        <button
          type="button"
          class="chapter-jump-trigger"
          v-bind="commandProps"
          :aria-expanded="open"
          aria-label="快速跳转到任意话"
          title="快速跳转到任意话"
        >
          <AppIcon name="search" size="xs" />
          <span class="chapter-jump-ratio">{{ activeOrdinalLabel }}/{{ chapterList.length }}</span>
          <AppIcon name="chevron-down" size="xs" />
        </button>
      </template>

      <template #content>
        <div class="chapter-jump-panel">
          <div class="chapter-jump-search">
            <input
              ref="jumpInputEl"
              v-model="jumpQuery"
              type="search"
              class="field-input chapter-jump-input"
              placeholder="输入话号（如 680）或标题，回车直达"
              aria-label="输入话号或标题关键词"
              @keydown.enter.prevent="submitJumpQuery"
            />
          </div>

          <div
            v-if="!trimmedJumpQuery && jumpSegments.length > 1"
            class="chapter-jump-segments"
            role="tablist"
            aria-label="百话分段"
          >
            <button
              v-for="seg in jumpSegments"
              :key="seg.segIdx"
              type="button"
              role="tab"
              class="chapter-segment-btn"
              :aria-selected="selectedSegment === seg.segIdx"
              :data-selected="selectedSegment === seg.segIdx"
              @click="selectSegment(seg.segIdx)"
            >
              {{ seg.label }}
            </button>
          </div>

          <div class="chapter-jump-list" role="listbox" aria-label="章节列表">
            <button
              v-for="chap in filteredJump.items"
              :key="chap.id"
              type="button"
              role="option"
              class="chapter-jump-item"
              :aria-selected="chap.id === activeId"
              :data-active="chap.id === activeId"
              @click="selectJumpChapter(chap.id)"
            >
              <span class="chapter-jump-idx">{{ chap.index }}</span>
              <span class="chapter-jump-name">{{ chap.title || `第 ${chap.index} 話` }}</span>
              <span class="chapter-jump-pages">{{ chap.page_count }} P</span>
            </button>

            <p v-if="filteredJump.items.length === 0" class="chapter-jump-empty">未找到匹配章节</p>
          </div>

          <div
            v-if="
              filteredJump.isSegmentTruncated ||
              (trimmedJumpQuery && filteredJump.total > JUMP_RENDER_LIMIT)
            "
            class="chapter-jump-footer"
          >
            <span v-if="filteredJump.isSegmentTruncated" class="chapter-jump-note">
              本段共 {{ filteredJump.total }} 话（展示 {{ filteredJump.items.length }} 话）
            </span>
            <span v-else class="chapter-jump-note">
              匹配 {{ filteredJump.total }} 话，仅显示前 {{ JUMP_RENDER_LIMIT }} 条
            </span>
            <button
              v-if="filteredJump.isSegmentTruncated"
              type="button"
              class="chapter-jump-expand"
              @click="segmentExpanded = true"
            >
              显示本段全部
            </button>
          </div>
        </div>
      </template>
    </AppPopover>
  </div>
</template>

<style scoped>
.chapter-switcher-shell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: var(--space-5) calc(-1 * var(--page-pad)) 0;
  border-bottom: 1px solid var(--line);
  min-width: 0;
}

.chapter-switcher-shell[data-pager='true'] {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  border-bottom: 0;
  align-self: center;
}

.chapter-switcher {
  --switcher-gap: var(--space-3);
  --fade-size: var(--space-6);
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--switcher-gap);
  overflow-x: auto;
  padding: var(--space-1) var(--space-1) var(--space-2);
  padding-inline: var(--page-pad);
  scroll-padding-inline: var(--fade-size);
  /* 滚动条对齐 UI：细轨道 + 朱砂细滑块，跟随主题 */
  scrollbar-width: thin;
  scrollbar-color: color-mix(in oklab, var(--accent) 45%, transparent) transparent;
}

.chapter-switcher::-webkit-scrollbar {
  height: 6px;
}

.chapter-switcher::-webkit-scrollbar-track {
  background: transparent;
}

.chapter-switcher::-webkit-scrollbar-thumb {
  background: color-mix(in oklab, var(--accent) 45%, transparent);
  border-radius: var(--radius-pill);
}

.chapter-switcher::-webkit-scrollbar-thumb:hover {
  background: var(--accent);
}

/* pager 模式：嵌在上一话/下一话之间 */
.chapter-switcher[data-pager='true'] {
  margin: 0;
  padding: var(--space-1);
}

.scroll-sentinel {
  flex: 0 0 1px;
  width: 1px;
  height: 1px;
  pointer-events: none;
}

.scroll-sentinel--start {
  margin-inline-end: calc(-1 * var(--switcher-gap));
}

.scroll-sentinel--end {
  margin-inline-start: calc(-1 * var(--switcher-gap));
}

.chapter-chip,
.chapter-edge-jump {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: var(--control-md);
  padding: 0 var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background-color: var(--paper-0);
  color: var(--ink-1);
  font-size: var(--text-sm);
  transition:
    border-color var(--duration-2) var(--ease-out),
    background-color var(--duration-2) var(--ease-out),
    color var(--duration-2) var(--ease-out);
}

.chapter-edge-jump {
  border-style: dashed;
  color: var(--ink-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.chapter-chip:hover,
.chapter-edge-jump:hover {
  border-color: var(--line-strong);
  color: var(--ink-0);
}

.chapter-chip[data-active='true'] {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-strong);
  box-shadow: var(--shadow-1);
}

.chapter-ordinal {
  display: grid;
  place-items: center;
  width: calc(var(--control-md) - var(--space-4));
  height: calc(var(--control-md) - var(--space-4));
  border-radius: 50%;
  background: var(--paper-2);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.chapter-chip[data-active='true'] .chapter-ordinal {
  background: var(--accent);
  color: var(--accent-contrast);
}

.chapter-title {
  white-space: nowrap;
  max-width: 13rem;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chapter-current {
  padding: var(--space-0-5) var(--space-2);
  border-radius: var(--radius-1);
  background: var(--accent);
  color: var(--accent-contrast);
  font-size: var(--text-caption);
}

.chapter-chip[data-state='past'] {
  opacity: 0.62;
}

.chapter-count {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-1);
  padding: var(--space-0-5) var(--space-2);
  border-radius: var(--radius-1);
  background: var(--paper-1);
}

.chapter-chip[data-active='true'] .chapter-count {
  background: color-mix(in oklab, var(--accent) 10%, var(--paper-1));
}

/* 外置快速跳话触发按钮与浮层 */
.chapter-jump-trigger {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  min-height: var(--control-md);
  padding: 0 var(--space-2-5);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  color: var(--ink-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  white-space: nowrap;
  transition:
    border-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.chapter-jump-trigger:hover,
.chapter-jump-trigger[aria-expanded='true'] {
  border-color: var(--accent);
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.chapter-jump-panel {
  display: grid;
  gap: var(--space-2-5);
  padding: var(--space-3);
}

.chapter-jump-input {
  min-height: var(--control-sm);
  font-size: var(--text-xs);
}

.chapter-jump-segments {
  display: flex;
  gap: var(--space-1-5);
  overflow-x: auto;
  padding-bottom: var(--space-1);
  scrollbar-width: thin;
}

.chapter-segment-btn {
  flex: 0 0 auto;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  background: var(--paper-1);
  color: var(--ink-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  white-space: nowrap;
}

.chapter-segment-btn[data-selected='true'] {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-strong);
  font-weight: 600;
}

.chapter-jump-list {
  display: grid;
  gap: var(--space-1);
  max-height: 16rem;
  overflow-y: auto;
  scrollbar-width: thin;
}

.chapter-jump-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  min-height: 2.25rem;
  padding: var(--space-1-5) var(--space-2-5);
  border: 1px solid transparent;
  border-radius: var(--radius-1);
  background: transparent;
  color: var(--ink-0);
  font-size: var(--text-xs);
  text-align: left;
}

.chapter-jump-item:hover {
  background: var(--paper-1);
  border-color: var(--line);
}

.chapter-jump-item[data-active='true'] {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent-strong);
  font-weight: 600;
}

.chapter-jump-idx {
  flex: 0 0 auto;
  min-width: 2.25rem;
  font-family: var(--font-mono);
  color: var(--ink-2);
}

.chapter-jump-item[data-active='true'] .chapter-jump-idx {
  color: var(--accent-strong);
}

.chapter-jump-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chapter-jump-pages {
  flex: 0 0 auto;
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.chapter-jump-empty {
  margin: 0;
  padding: var(--space-4) var(--space-2);
  text-align: center;
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.chapter-jump-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--line);
}

.chapter-jump-note {
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.chapter-jump-expand {
  border: 0;
  background: transparent;
  padding: var(--space-1) var(--space-1-5);
  color: var(--accent-strong);
  font-size: var(--text-caption);
  font-weight: 600;
  cursor: pointer;
}

/* 现代 CSS 滚动驱动边缘渐隐提示（零滚动监听、零 Vue 重渲染） */
@keyframes chapter-fade-start {
  to {
    --mask-left: var(--fade-size);
  }
}

@keyframes chapter-fade-end {
  from {
    --mask-right: var(--fade-size);
  }
}

@supports (animation-timeline: scroll()) and (mask: linear-gradient(black, black) no-clip subtract) {
  .chapter-switcher {
    mask:
      linear-gradient(black, black) no-clip subtract,
      linear-gradient(to right, black, transparent) 0 0 / var(--mask-left) 100% no-repeat no-clip,
      linear-gradient(to right, transparent, black) 100% 0 / var(--mask-right) 100% no-repeat
        no-clip;
    animation:
      chapter-fade-start linear both,
      chapter-fade-end linear both;
    animation-timeline: scroll(self inline);
    animation-range:
      0 var(--fade-size),
      calc(100% - var(--fade-size)) 100%;
  }
}

/* 回退分支：IntersectionObserver 哨兵驱动 data-scroll-left/right */
@supports not (
  (animation-timeline: scroll()) and (mask: linear-gradient(black, black) no-clip subtract)
) {
  .chapter-switcher {
    -webkit-mask-image: linear-gradient(
      to right,
      transparent 0%,
      black var(--mask-left),
      black calc(100% - var(--mask-right)),
      transparent 100%
    );
    mask-image: linear-gradient(
      to right,
      transparent 0%,
      black var(--mask-left),
      black calc(100% - var(--mask-right)),
      transparent 100%
    );
    transition:
      --mask-left var(--duration-1) var(--ease-out),
      --mask-right var(--duration-1) var(--ease-out);
  }

  .chapter-switcher[data-scroll-left='true'] {
    --mask-left: var(--fade-size);
  }

  .chapter-switcher[data-scroll-right='true'] {
    --mask-right: var(--fade-size);
  }
}

@media (max-width: 680px) {
  .chapter-switcher-shell {
    margin-inline: calc(-1 * var(--space-3-5));
  }

  .chapter-switcher-shell[data-pager='true'] {
    margin-inline: 0;
  }

  .chapter-switcher {
    --switcher-gap: var(--space-2);
    padding-inline: var(--space-3-5);
  }

  .chapter-switcher[data-pager='true'] {
    padding-inline: var(--space-1);
  }

  .chapter-chip,
  .chapter-edge-jump,
  .chapter-jump-trigger {
    min-height: 2.75rem; /* 44px 移动端触控底线 */
    font-size: var(--text-xs);
  }

  .chapter-chip,
  .chapter-edge-jump {
    padding: 0 var(--space-3);
    gap: var(--space-2);
  }

  .chapter-title {
    max-width: 8.5rem;
  }
}
</style>

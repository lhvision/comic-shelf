<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onScopeDispose,
  onWatcherCleanup,
  useTemplateRef,
  watch,
} from 'vue'
import { useEventListener, useResizeObserver } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import ChapterJumpPopover from '@/components/detail/ChapterJumpPopover.vue'
import { prefersReducedMotion } from '@/utils/is'
import { clamp } from '@/utils/math'
import type { Chapter } from '@/types'

const WINDOW_THRESHOLD = 48
const WINDOW_RADIUS = 16
const WINDOW_SIZE = WINDOW_RADIUS * 2 + 1

/**
 * 多章节详情页的「章节切换条」 —— 横向 chips，标出章节序数 / 标题 / 页数。
 * 单章节（chapters.length <= 1）时不渲染任何内容，保持旧详情页外观。
 * 纯展示组件：选中态由父级 activeId 驱动，切换以 emit 上抛。
 *
 * - 超长连载窗口裁剪（> 48 话）：仅挂载以当前激活章节为中心的 ±16 话（最多 33 枚 chip），
 *   消除数千节点 DOM 与 O(N²) 查找开销，并在外侧挂载 `ChapterJumpPopover` 快速跳话浮层。
 * - 选中 chip 的横向居中：通过几何差值计算当前激活卡片在容器视口的中心位置。
 *   首屏挂载 / 尺寸变化采用瞬间直达（behavior: 'auto'），用户切话采用平滑平移（减弱动效时退化为 auto）。
 * - 边缘渐隐提示：优先使用纯 CSS `animation-timeline: scroll(self inline)` + `@property` 遮罩，
 *   不支持时回退至首尾哨兵 `IntersectionObserver`，全程零滚动监听重渲染。
 * - 键盘操作：左/右方向键与 Home/End 在全书章节间移动，窗口滑动后自动还原焦点并避免强制抢滚。
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
const jumpPopoverEl = useTemplateRef<InstanceType<typeof ChapterJumpPopover>>('jumpPopoverEl')
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

const leftEdgeRange = computed(() => {
  const start = windowRange.value.start
  if (!isWindowed.value || start <= 0) return ''
  const first = chapterList.value[0]?.index ?? 1
  const last = chapterList.value[start - 1]?.index ?? start
  return first === last ? String(first) : `${first}–${last}`
})

const rightEdgeRange = computed(() => {
  const { end } = windowRange.value
  const len = chapterList.value.length
  if (!isWindowed.value || end >= len) return ''
  const first = chapterList.value[end]?.index ?? end + 1
  const last = chapterList.value[len - 1]?.index ?? len
  return first === last ? String(first) : `${first}–${last}`
})

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
let isDisposed = false
let pendingRafId: number | null = null
let pendingFocusId: string | null = null

function cancelPendingRaf() {
  if (pendingRafId !== null && typeof cancelAnimationFrame === 'function') {
    cancelAnimationFrame(pendingRafId)
  }
  pendingRafId = null
}

function scheduleScrollToActive(smooth: boolean, onAfter?: () => void) {
  cancelPendingRaf()
  pendingRafId = requestAnimationFrame(() => {
    pendingRafId = null
    scrollToActive(smooth)
    onAfter?.()
  })
}

onScopeDispose(() => {
  isDisposed = true
  cancelPendingRaf()
})

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
  if (isDisposed) return
  scheduleScrollToActive(false, () => {
    hasMounted = true
  })
})

watch(
  () => [props.activeId, chapterList.value.length] as const,
  async ([newId, len], [oldId]) => {
    let cancelled = false
    onWatcherCleanup(() => {
      cancelled = true
      cancelPendingRaf()
    })
    if (!newId || len === 0) {
      pendingFocusId = null
      return
    }
    await nextTick()
    if (cancelled || isDisposed) return
    if (pendingFocusId === newId) {
      buttonEls.get(newId)?.focus({ preventScroll: true })
    }
    pendingFocusId = null
    const isUserAction = hasMounted && oldId !== undefined && newId !== oldId
    scheduleScrollToActive(isUserAction)
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
    pendingFocusId = nextId
    emit('change', nextId)
  }
})

function selectChapter(id: string) {
  pendingFocusId = null
  emit('change', id)
}

function chapterLabel(chapter: Chapter) {
  return chapter.title ? `第 ${chapter.index} 話 · ${chapter.title}` : `第 ${chapter.index} 話`
}

/** O(1) 索引态判定：已翻过 / 当前 / 未翻到 */
function stateByIndex(idx: number): 'past' | 'active' | 'upcoming' {
  if (activeIndex.value < 0) return 'upcoming'
  if (idx === activeIndex.value) return 'active'
  return idx < activeIndex.value ? 'past' : 'upcoming'
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
        v-if="leftEdgeRange"
        type="button"
        class="chapter-edge-jump chapter-edge-jump--start"
        :title="`前面还有 ${windowRange.start} 话，点击快速跳话`"
        :aria-label="`前面还有 ${windowRange.start} 话，点击跳话`"
        @click="jumpPopoverEl?.openAt(0)"
      >
        <AppIcon name="more" size="xs" />
        <span class="chapter-edge-range">{{ leftEdgeRange }}</span>
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
        @click="selectChapter(chapter.id)"
      >
        <span class="chapter-ordinal">{{ chapter.index }}</span>
        <span class="chapter-title">{{ chapterLabel(chapter) }}</span>
        <span v-if="activeId === chapter.id" class="chapter-current" aria-hidden="true">当前</span>
        <span class="chapter-count">{{ chapter.page_count }} P</span>
      </button>

      <button
        v-if="rightEdgeRange"
        type="button"
        class="chapter-edge-jump chapter-edge-jump--end"
        :title="`后面还有 ${chapterList.length - windowRange.end} 话，点击快速跳话`"
        :aria-label="`后面还有 ${chapterList.length - windowRange.end} 话，点击跳话`"
        @click="jumpPopoverEl?.openAt(windowRange.end)"
      >
        <AppIcon name="more" size="xs" />
        <span class="chapter-edge-range">{{ rightEdgeRange }}</span>
      </button>

      <span
        v-if="!supportsScrollTimeline"
        ref="endSentinelEl"
        class="scroll-sentinel scroll-sentinel--end"
        aria-hidden="true"
      />
    </div>

    <ChapterJumpPopover
      v-if="isWindowed"
      ref="jumpPopoverEl"
      :chapters="chapterList"
      :active-index="activeIndex"
      :active-id="activeId"
      @change="selectChapter"
    />
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
  .chapter-edge-jump {
    min-height: 2.75rem; /* 44px 移动端触控底线 */
    font-size: var(--text-xs);
    padding: 0 var(--space-3);
    gap: var(--space-2);
  }

  .chapter-title {
    max-width: 8.5rem;
  }
}
</style>

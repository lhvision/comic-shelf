<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useEventListener, useResizeObserver, useScroll } from '@vueuse/core'
import { clamp } from '@/utils/math'
import type { Chapter } from '@/types'

/**
 * 多章节详情页的「章节切换」条 —— 横向 chips，标出章节序数 / 标题 / 页数。
 * 单章节（chapters.length <= 1）时不渲染任何内容，保持旧详情页外观。
 * 纯展示组件：选中态由父级 activeId 驱动，切换以 emit 上抛。
 *
 * - 选中 chip 的横向居中：通过几何差值计算当前激活卡片在容器视口的中心位置。
 *   首屏挂载 / 从阅读器返回初始定位采用瞬间直达（behavior: 'auto'），避免长篇动画眩晕与掉帧；
 *   用户交互切话采用平滑平移（behavior: 'smooth'）。
 * - 容器缩放自愈：监听容器尺寸变化（useResizeObserver），维持当前激活项始终居中。
 * - 键盘操作：左/右方向键在章节按钮间移动（复用既有的 `useEventListener`，
 *   不手写 addEventListener/disconnect）。
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
const buttonEls: Record<string, HTMLElement | null> = {}

const scrollBehavior = ref<ScrollBehavior>('auto')

// @vueuse/core 14.x：useScroll 响应式绑定横向容器与动态 behavior。
const { x, arrivedState } = useScroll(listEl, { behavior: scrollBehavior })

// 防御：父级必须解构 unwrap 后传入；万一传了 Ref 或 undefined，这里兜底为空数组。
const chapterList = computed(() => (Array.isArray(props.chapters) ? props.chapters : []))

const activeIndex = computed(() => chapterList.value.findIndex((c) => c.id === props.activeId))

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
  const el = buttonEls[activeKey]
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

  scrollBehavior.value = smooth ? 'smooth' : 'auto'
  x.value = targetLeft
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
    void nextTick(() => buttonEls[nextId]?.focus())
  }
})

function chapterLabel(chapter: Chapter) {
  return chapter.title ? `第 ${chapter.index} 話 · ${chapter.title}` : `第 ${chapter.index} 話`
}

/** T09 语义增强：已翻过 / 当前 / 未翻到，用于 chip 的微弱视觉区分。 */
function chapterState(id: string): 'past' | 'active' | 'upcoming' {
  const idx = chapterList.value.findIndex((c) => c.id === id)
  if (idx < 0 || activeIndex.value < 0) return 'upcoming'
  if (idx === activeIndex.value) return 'active'
  return idx < activeIndex.value ? 'past' : 'upcoming'
}
</script>

<template>
  <div
    v-if="chapterList.length > 1"
    ref="listEl"
    class="chapter-switcher"
    :data-pager="inPager"
    :data-scroll-left="!arrivedState.left"
    :data-scroll-right="!arrivedState.right"
    role="group"
    aria-label="章节"
  >
    <button
      v-for="chapter in chapterList"
      :key="chapter.id"
      :ref="(el) => (buttonEls[chapter.id] = el as HTMLElement | null)"
      type="button"
      :aria-pressed="activeId === chapter.id"
      :data-active="activeId === chapter.id"
      :data-state="chapterState(chapter.id)"
      :title="chapterLabel(chapter)"
      @click="emit('change', chapter.id)"
    >
      <span class="chapter-ordinal">{{ chapter.index }}</span>
      <span class="chapter-title">{{ chapterLabel(chapter) }}</span>
      <span v-if="activeId === chapter.id" class="chapter-current" aria-hidden="true">当前</span>
      <span class="chapter-count">{{ chapter.page_count }} P</span>
    </button>
  </div>
</template>

<style scoped>
.chapter-switcher {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  overflow-x: auto;
  padding: var(--space-1) var(--space-1) var(--space-2);
  margin: var(--space-5) calc(-1 * var(--page-pad)) 0;
  padding-inline: var(--page-pad);
  border-bottom: 1px solid var(--line);
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
  border-radius: 999px;
}

.chapter-switcher::-webkit-scrollbar-thumb:hover {
  background: var(--accent);
}

/* pager 模式：嵌在上一话/下一话之间 */
.chapter-switcher[data-pager='true'] {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  padding: var(--space-1);
  border-bottom: 0;
  align-self: center;
}

.chapter-switcher button {
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

.chapter-switcher button:hover {
  border-color: var(--line-strong);
  color: var(--ink-0);
}

.chapter-switcher button[data-active='true'] {
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

.chapter-switcher button[data-active='true'] .chapter-ordinal {
  background: var(--accent);
  color: var(--paper-0);
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
  color: var(--paper-0);
  font-size: var(--text-caption);
}

.chapter-switcher button[data-state='past'] {
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

.chapter-switcher button[data-active='true'] .chapter-count {
  background: color-mix(in oklab, var(--accent) 10%, var(--paper-1));
}

/* 动态边缘渐隐提示（遵循 DESIGN_NOTES.md 与 CSS_RADAR 规范） */
.chapter-switcher[data-scroll-right='true'] {
  -webkit-mask-image: linear-gradient(
    to right,
    black calc(100% - var(--space-6)),
    transparent 100%
  );
  mask-image: linear-gradient(to right, black calc(100% - var(--space-6)), transparent 100%);
}

.chapter-switcher[data-scroll-left='true'] {
  -webkit-mask-image: linear-gradient(to right, transparent 0%, black var(--space-6));
  mask-image: linear-gradient(to right, transparent 0%, black var(--space-6));
}

.chapter-switcher[data-scroll-left='true'][data-scroll-right='true'] {
  -webkit-mask-image: linear-gradient(
    to right,
    transparent 0%,
    black var(--space-6),
    black calc(100% - var(--space-6)),
    transparent 100%
  );
  mask-image: linear-gradient(
    to right,
    transparent 0%,
    black var(--space-6),
    black calc(100% - var(--space-6)),
    transparent 100%
  );
}

@media (prefers-reduced-motion: reduce) {
  .chapter-switcher {
    -webkit-mask-image: none !important;
    mask-image: none !important;
  }
}

@media (max-width: 680px) {
  .chapter-switcher {
    margin-inline: calc(-1 * var(--space-3-5));
    padding-inline: var(--space-3-5);
    gap: var(--space-2);
  }

  .chapter-switcher button {
    padding: 0 var(--space-3);
    gap: var(--space-2);
    min-height: 2.75rem; /* 44px 移动端触控底线 */
    font-size: var(--text-xs);
  }

  .chapter-title {
    max-width: 8.5rem;
  }
}
</style>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useEventListener, useScroll } from '@vueuse/core'
import type { Chapter } from '@/types'

/**
 * 多章节详情页的「章节切换」条 —— 横向 chips，标出章节序数 / 标题 / 页数。
 * 单章节（chapters.length <= 1）时不渲染任何内容，保持旧详情页外观。
 * 纯展示组件：选中态由父级 activeId 驱动，切换以 emit 上抛。
 *
 * - 选中 chip 的横向居中：VueUse `useScroll` 的 smooth 滚动（替代手写
 *   requestAnimationFrame），容器可横向滚动时自动把当前章节滚进视野中心。
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

const listEl = ref<HTMLElement | null>(null)
const buttonEls = ref<Record<string, HTMLElement | null>>({})

const { scrollTo } = useScroll(listEl, { behavior: 'smooth' })

// 防御：父级必须解构 unwrap 后传入；万一传了 Ref 或 undefined，这里兜底为空数组。
const chapterList = computed(() => (Array.isArray(props.chapters) ? props.chapters : []))

const activeIndex = computed(() => chapterList.value.findIndex((c) => c.id === props.activeId))

watch(activeIndex, async (idx) => {
  if (idx < 0) return
  await nextTick()
  const el = buttonEls.value[props.activeId ?? '']
  const container = listEl.value
  if (!el || !container || container.scrollWidth <= container.clientWidth) return
  const left = Math.max(0, el.offsetLeft - (container.clientWidth - el.offsetWidth) / 2)
  scrollTo({ left })
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
    nextId =
      chapterList.value[Math.min(Math.max(idx + delta, 0), chapterList.value.length - 1)]?.id ??
      null
  }

  if (nextId && nextId !== props.activeId) {
    emit('change', nextId)
    void nextTick(() => buttonEls.value[nextId]?.focus())
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
    role="group"
    aria-label="章节"
  >
    <span class="chapter-progress" role="status">
      第 {{ activeIndex + 1 }} 話 / 共 {{ chapterList.length }} 話
    </span>
    <button
      v-for="chapter in chapterList"
      :key="chapter.id"
      :ref="(el) => (buttonEls[chapter.id] = el)"
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
  background: var(--paper-0);
  color: var(--ink-1);
  font-size: var(--text-sm);
  transition:
    border-color var(--duration-2) var(--ease-out),
    background var(--duration-2) var(--ease-out),
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

.chapter-progress {
  position: sticky;
  left: 0;
  z-index: 2;
  flex: 0 0 auto;
  align-self: center;
  padding: var(--space-1) var(--space-3);
  border-radius: 999px;
  background: var(--paper-1);
  border: 1px solid var(--line-strong);
  color: var(--ink-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  white-space: nowrap;
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

@media (max-width: 640px) {
  .chapter-title {
    max-width: 8rem;
  }
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

@media (max-width: 640px) {
  .chapter-switcher {
    margin-inline: calc(-1 * var(--space-4));
    padding-inline: var(--space-4);
  }
}
</style>

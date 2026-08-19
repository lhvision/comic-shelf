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
const props = defineProps<{
  chapters: Chapter[]
  activeId: string | null
}>()

const emit = defineEmits<{ change: [id: string] }>()

const listEl = ref<HTMLElement | null>(null)
const buttonEls = ref<Record<string, HTMLElement | null>>({})

const { scrollTo } = useScroll(listEl, { behavior: 'smooth' })

const activeIndex = computed(() => props.chapters.findIndex((c) => c.id === props.activeId))

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
  if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
  const idx = activeIndex.value
  if (idx < 0) return
  event.preventDefault()
  const delta = event.key === 'ArrowRight' ? 1 : -1
  const next = Math.min(Math.max(idx + delta, 0), props.chapters.length - 1)
  const target = props.chapters[next]
  if (!target || target.id === props.activeId) return
  emit('change', target.id)
  void nextTick(() => buttonEls.value[target.id]?.focus())
})

function chapterLabel(chapter: Chapter) {
  return chapter.title ? `第 ${chapter.index} 話 · ${chapter.title}` : `第 ${chapter.index} 話`
}

/** T09 语义增强：已翻过 / 当前 / 未翻到，用于 chip 的微弱视觉区分。 */
function chapterState(id: string): 'past' | 'active' | 'upcoming' {
  const idx = props.chapters.findIndex((c) => c.id === id)
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
    role="group"
    aria-label="章节"
  >
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
  gap: var(--space-3);
  overflow-x: auto;
  padding: var(--space-1) var(--space-1) var(--space-2);
  margin: var(--space-5) calc(-1 * var(--page-pad)) 0;
  padding-inline: var(--page-pad);
  scrollbar-width: thin;
  border-bottom: 1px solid var(--line);
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
  width: 1.75rem;
  height: 1.75rem;
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

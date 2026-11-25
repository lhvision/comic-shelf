<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import AppPopover from '@/components/AppPopover.vue'
import { clamp } from '@/utils/math'
import type { Chapter } from '@/types'

const JUMP_SEGMENT_SIZE = 100
const JUMP_RENDER_LIMIT = 40
const ACTIVE_TOP_CONTEXT_OFFSET = Math.floor(JUMP_RENDER_LIMIT / 3)

/**
 * 超长连载章节切换条的「快速跳话浮层」。
 * - 基于原生 Top Layer `AppPopover` 承载，免受父级 `overflow` 与 `z-index` 截断；
 * - 支持按话号（含「第 N 话」形态）或标题关键词实时过滤，回车直达首条匹配；
 * - 支持按百话自动分段，默认截断为最多 40 条可视项并支持一键展开当前整段。
 */
const props = defineProps<{
  chapters: Chapter[]
  activeIndex: number
  activeId: string | null
}>()

const emit = defineEmits<{ change: [id: string] }>()

const jumpOpen = ref(false)
const jumpQuery = ref('')
const selectedSegment = ref(0)
const segmentExpanded = ref(false)
const jumpInputEl = useTemplateRef<HTMLInputElement>('jumpInputEl')

let pendingSegmentOverride: number | null = null

const activeOrdinalLabel = computed(
  () => props.chapters[props.activeIndex]?.index ?? props.chapters[0]?.index ?? 1,
)

const jumpSegments = computed(() => {
  const len = props.chapters.length
  const count = Math.ceil(len / JUMP_SEGMENT_SIZE)
  return Array.from({ length: count }, (_, segIdx) => {
    const startIdx = segIdx * JUMP_SEGMENT_SIZE
    const endIdx = Math.min(len, startIdx + JUMP_SEGMENT_SIZE)
    const firstOrdinal = props.chapters[startIdx]?.index ?? startIdx + 1
    const lastOrdinal = props.chapters[endIdx - 1]?.index ?? endIdx
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
  const list = props.chapters
  const q = trimmedJumpQuery.value
  if (!q) {
    const seg = jumpSegments.value[selectedSegment.value] ?? jumpSegments.value[0]
    if (!seg) return { items: [] as Chapter[], total: 0, isSegmentTruncated: false }
    const slice = list.slice(seg.startIdx, seg.endIdx)
    if (segmentExpanded.value || slice.length <= JUMP_RENDER_LIMIT) {
      return { items: slice, total: slice.length, isSegmentTruncated: false }
    }
    const localActive =
      props.activeIndex >= seg.startIdx && props.activeIndex < seg.endIdx
        ? props.activeIndex - seg.startIdx
        : 0
    const offset =
      localActive >= JUMP_RENDER_LIMIT
        ? Math.min(
            slice.length - JUMP_RENDER_LIMIT,
            Math.max(0, localActive - ACTIVE_TOP_CONTEXT_OFFSET),
          )
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

  const exactMatches: Chapter[] = []
  const matches: Chapter[] = []
  for (const chapter of list) {
    if (exactOrdinal !== null && chapter.index === exactOrdinal) {
      exactMatches.push(chapter)
      continue
    }
    if (String(chapter.index).includes(q) || chapter.title.toLowerCase().includes(q)) {
      matches.push(chapter)
    }
  }
  const ordered = exactMatches.length > 0 ? [...exactMatches, ...matches] : matches
  return {
    items: ordered.slice(0, JUMP_RENDER_LIMIT),
    total: ordered.length,
    isSegmentTruncated: false,
  }
})

function segmentIndexFor(chapIdx: number): number {
  const maxIdx = Math.max(0, props.chapters.length - 1)
  return Math.floor(clamp(chapIdx, 0, maxIdx) / JUMP_SEGMENT_SIZE)
}

function resetJumpPanel(segIdx: number) {
  pendingSegmentOverride = null
  selectedSegment.value = segIdx
  segmentExpanded.value = false
  jumpQuery.value = ''
  void nextTick(() => jumpInputEl.value?.focus())
}

/**
 * 打开快速跳话浮层并定位到指定数组下标所属分段（缺省为当前激活章节所在分段）。
 *
 * @param targetIdx 目标章节在 `chapters` 中的数组下标。
 */
function openAt(targetIdx?: number) {
  const targetSeg = segmentIndexFor(targetIdx ?? Math.max(0, props.activeIndex))
  if (jumpOpen.value) {
    resetJumpPanel(targetSeg)
    return
  }
  pendingSegmentOverride = targetSeg
  jumpOpen.value = true
}

function onJumpOpen() {
  resetJumpPanel(pendingSegmentOverride ?? segmentIndexFor(Math.max(0, props.activeIndex)))
}

function onJumpClose() {
  pendingSegmentOverride = null
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

defineExpose({ openAt })
</script>

<template>
  <AppPopover
    v-model:open="jumpOpen"
    side="bottom"
    align="end"
    width="min(22rem, calc(100vw - 2rem))"
    aria-label="快速跳话"
    @open="onJumpOpen"
    @close="onJumpClose"
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
        <span>{{ activeOrdinalLabel }}/{{ chapters.length }}</span>
        <AppIcon name="chevron-down" size="xs" />
      </button>
    </template>

    <template #content>
      <div class="chapter-jump-panel">
        <input
          ref="jumpInputEl"
          v-model="jumpQuery"
          type="search"
          class="field-input chapter-jump-input"
          placeholder="输入话号（如 680）或标题，回车直达"
          aria-label="输入话号或标题关键词"
          @keydown.enter.prevent="submitJumpQuery"
        />

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

        <div
          v-if="filteredJump.items.length > 0"
          class="chapter-jump-list"
          role="listbox"
          aria-label="章节列表"
        >
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
        </div>
        <p v-else class="chapter-jump-empty">未找到匹配章节</p>

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
</template>

<style scoped>
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

@media (max-width: 680px) {
  .chapter-jump-trigger {
    min-height: 2.75rem; /* 44px 移动端触控底线 */
    font-size: var(--text-xs);
  }
}
</style>

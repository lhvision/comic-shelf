<script setup lang="ts">
/**
 * TagFilterBar.vue — 书架多维状态与分类标签筛选工具栏
 *
 * @description
 * 提供藏书多维筛选能力：
 * 1. 「只看喜欢」微件开关（独立正交维度）
 * 2. 「全部 / 在读 / 已读」分段选择器（SegmentedTabs，互斥单选，同步 URL ?status=）
 * 3. 分类标签 Chips 与高频/溢出收纳浮层（前 8 个默认外露，其余收纳至基于 HTML Popover API 的顶层气泡浮层）
 *
 * 架构重构（ADR 0014 演进、Trace-20260910 性能落地与 Impeccable A 轨评审）：
 * - 彻底废弃在文档流中推挤书架卡片的 grid-template-rows 尺寸插值；
 * - 溢出标签全面收敛至基于 HTML Popover API + CSS Anchor Positioning 的 AppPopover 顶层浮层；
 * - 页面高度保持严格静止，0 页面推挤，0 几何重排，彻底消除 144Hz 屏幕与集成显卡下的连续掉帧；
 * - 补齐无障碍焦点归还（Focus Restoration，WCAG 2.1 2.4.3）与溢出标签双向清除闭环（Header Clear / Pinned Active Tag / Close Restoration）。
 *
 * @prop {boolean} favoritesOnly - 是否仅筛选已加入喜欢的藏书
 * @prop {ReadingStatus} [readingStatus='all'] - 当前选中的阅读状态（'all' | 'reading' | 'completed'）
 * @prop {string} activeTag - 当前激活的分类标签名称（空表示全部标签）
 * @prop {Array<[string, number]>} tagCounts - 全库或当前来源前 18/30 高频标签及其计数
 * @prop {number} filteredCount - 当前筛选命中的条目数
 *
 * @emit toggleFavorites - 切换喜欢状态
 * @emit update:readingStatus - 阅读状态变更事件（'all' | 'reading' | 'completed'）
 * @emit selectTag - 选中指定标签（传空表示取消标签筛选）
 * @emit clearTag - 清空标签筛选
 */
import { computed, nextTick, ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import AppChip from '@/components/AppChip.vue'
import AppPopover from '@/components/AppPopover.vue'
import SegmentedTabs, { type TabItem } from '@/components/SegmentedTabs.vue'
import type { ReadingStatus } from '@/types'

const trayExpanded = defineModel<boolean>('trayExpanded', { default: false })

export interface TagFilterBarProps {
  favoritesOnly: boolean
  readingStatus?: ReadingStatus
  activeTag: string
  /** [标签, 数量] 有序列表，按出现次数降序 */
  tagCounts: Array<[string, number]>
  /** 当前筛选命中的数量（用于提示文案） */
  filteredCount: number
}

const props = withDefaults(defineProps<TagFilterBarProps>(), {
  readingStatus: 'all',
})

const emit = defineEmits<{
  toggleFavorites: []
  'update:readingStatus': [status: ReadingStatus]
  selectTag: [tag: string]
  clearTag: []
}>()

const readingStatusTabs: TabItem<ReadingStatus>[] = [
  { key: 'all', label: '全部' },
  { key: 'reading', label: '在读' },
  { key: 'completed', label: '已读' },
]

function onReadingStatusChange(status: ReadingStatus) {
  emit('update:readingStatus', status)
}

/** 默认展示的高频标签数（连「全部」一起 ≤9 个 chip） */
const VISIBLE_TAGS = 8

const moreCount = computed(() => Math.max(0, props.tagCounts.length - VISIBLE_TAGS))
const primaryTags = computed(() => props.tagCounts.slice(0, VISIBLE_TAGS))
const overflowTags = computed(() => props.tagCounts.slice(VISIBLE_TAGS))

/** 当前激活标签是否位于溢出标签列表中 */
const isOverflowActive = computed(() =>
  Boolean(props.activeTag && overflowTags.value.some(([t]) => t === props.activeTag)),
)

/** 当前激活标签对应的数量统计 */
const activeTagCount = computed(() => {
  if (!props.activeTag) return undefined
  const match = props.tagCounts.find(([t]) => t === props.activeTag)
  return match ? match[1] : undefined
})

/** 「更多标签」按钮文案动态计算 */
const moreButtonLabel = computed(() => {
  if (trayExpanded.value) return '收起标签'
  if (isOverflowActive.value) return `标签：${props.activeTag}`
  return `更多 · ${moreCount.value}`
})

/** 触发器元素引用（用于浮层关闭后的焦点归还） */
const triggerChipRef = ref<InstanceType<typeof AppChip> | null>(null)

function focusTrigger() {
  nextTick(() => {
    const raw = triggerChipRef.value
    const el = raw && typeof raw === 'object' && '$el' in raw ? (raw as { $el: unknown }).$el : raw
    if (el instanceof HTMLElement) {
      el.focus()
    }
  })
}

function selectTag(tag: string) {
  emit('selectTag', tag === props.activeTag ? '' : tag)
}

function clearFilter() {
  emit('selectTag', '')
  emit('clearTag')
}
</script>

<template>
  <div class="filter-toolbar">
    <div class="filter-cluster cluster" aria-label="书库筛选与标签">
      <AppChip class="favorite-filter" :pressed="favoritesOnly" @click="emit('toggleFavorites')">
        <template #prefix>
          <AppIcon class="heart-icon" :name="favoritesOnly ? 'heart-filled' : 'heart'" size="xs" />
        </template>
        <span>只看喜欢</span>
      </AppChip>

      <span class="filter-divider" aria-hidden="true" />

      <SegmentedTabs
        class="reading-status-tabs"
        :model-value="readingStatus"
        :items="readingStatusTabs"
        size="sm"
        aria-label="阅读状态筛选"
        @update:model-value="onReadingStatusChange"
      />

      <span v-if="tagCounts.length" class="filter-divider" aria-hidden="true" />

      <template v-if="tagCounts.length">
        <AppChip :pressed="activeTag === ''" @click="clearFilter"> 全部 </AppChip>
        <AppChip
          v-for="[tag, count] in primaryTags"
          :key="tag"
          :pressed="activeTag === tag"
          :count="count"
          @click="selectTag(tag)"
        >
          {{ tag }}
        </AppChip>

        <!-- 溢出次级标签：基于 HTML Popover API + CSS Anchor Positioning 的顶层气泡浮层 -->
        <AppPopover
          v-if="moreCount > 0"
          v-model:open="trayExpanded"
          side="bottom"
          align="start"
          arrow
          width="min(30rem, calc(100vw - 2rem))"
          aria-label="更多分类标签"
          role="dialog"
          @close="focusTrigger"
        >
          <template #default="{ open, targetId }">
            <AppChip
              ref="triggerChipRef"
              class="more-tags"
              :class="{ 'is-active-filter': isOverflowActive }"
              :pressed="isOverflowActive"
              :aria-expanded="open"
              :aria-controls="targetId"
              :commandfor="targetId"
              command="toggle-popover"
            >
              <span>{{ moreButtonLabel }}</span>
              <template #suffix>
                <AppIcon
                  name="chevron-down"
                  size="xs"
                  class="more-chevron"
                  :class="{ 'is-rotated': open }"
                />
              </template>
            </AppChip>
          </template>

          <template #content>
            <div class="overflow-popover-panel">
              <div class="overflow-popover-header">
                <div class="overflow-title-group">
                  <span class="overflow-title">更多分类标签</span>
                  <span class="overflow-meta">{{ moreCount }} 个次级标签</span>
                </div>
                <button
                  v-if="isOverflowActive"
                  type="button"
                  class="overflow-clear-btn"
                  @click="clearFilter"
                >
                  清除筛选
                </button>
              </div>

              <!-- 置顶当前已激活的次级标签 -->
              <div v-if="isOverflowActive" class="overflow-active-row">
                <span class="overflow-active-label">当前在看：</span>
                <AppChip
                  pressed
                  removable
                  remove-aria-label="清除当前次级标签筛选"
                  :count="activeTagCount"
                  @remove="clearFilter"
                  @click="clearFilter"
                >
                  {{ activeTag }}
                </AppChip>
              </div>

              <div class="overflow-cluster cluster">
                <AppChip
                  v-for="[tag, count] in overflowTags"
                  :key="tag"
                  :pressed="activeTag === tag"
                  :count="count"
                  @click="selectTag(tag)"
                >
                  {{ tag }}
                </AppChip>
              </div>
            </div>
          </template>
        </AppPopover>
      </template>
    </div>

    <p v-if="activeTag" class="filter-note">
      正在查看标签「{{ activeTag }}」的 {{ filteredCount }} 本
      <button class="clear-btn" type="button" @click="clearFilter">清除筛选</button>
    </p>
  </div>
</template>

<style scoped>
.filter-toolbar {
  padding: var(--space-4) 0 var(--space-2);
}

.filter-cluster {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.favorite-filter {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.reading-status-tabs {
  margin-inline: 0;
}

.favorite-filter .heart-icon {
  width: 0.85rem;
  height: 0.85rem;
  fill: transparent;
  stroke: currentColor;
  stroke-width: 2;
  transition: fill var(--duration-1) var(--ease-out);
}

.favorite-filter[aria-pressed='true'] .heart-icon {
  fill: currentColor;
}

.filter-divider {
  width: 1px;
  height: 1.25rem;
  background: var(--line-strong);
  margin-inline: var(--space-1);
}

.more-tags {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-mono);
}

.more-tags.is-active-filter {
  font-weight: 600;
}

.more-chevron {
  transition: transform var(--duration-2) var(--ease-spring);
}

.more-chevron.is-rotated {
  transform: rotate(180deg);
}

/* 溢出标签顶层浮层内容区 */
.overflow-popover-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4) var(--space-4);
}

.overflow-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--line);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.overflow-title-group {
  display: inline-flex;
  align-items: baseline;
  gap: var(--space-2);
}

.overflow-title {
  font-weight: 600;
  color: var(--ink-1);
}

.overflow-meta {
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.overflow-clear-btn {
  background: transparent;
  border: none;
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.overflow-clear-btn:hover {
  color: var(--accent);
}

.overflow-active-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1-5) var(--space-2);
  background: color-mix(in oklab, var(--paper-1) 70%, transparent);
  border-radius: var(--radius-1);
}

.overflow-active-label {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.overflow-cluster {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  max-height: min(50vh, 22rem);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: var(--space-1);
}

@media (prefers-reduced-motion: reduce) {
  .more-chevron {
    transition: none !important;
  }
}

.filter-note {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--paper-1) 60%, transparent);
  color: var(--ink-1);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
}

.clear-btn {
  background: transparent;
  color: var(--accent-strong);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
  padding: 0;
  font: inherit;
}
</style>

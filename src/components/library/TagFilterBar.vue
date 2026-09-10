<script setup lang="ts">
/**
 * TagFilterBar.vue — 书架多维状态与分类标签筛选工具栏
 *
 * @description
 * 提供藏书多维筛选能力：
 * 1. 「只看喜欢」微件开关（独立正交维度）
 * 2. 「全部 / 在读 / 已读」分段选择器（SegmentedTabs，互斥单选，同步 URL ?status=）
 * 3. 分类标签 Chips 与高频/溢出折叠抽屉（前 8 个默认外露，其余折叠入抽屉）
 *
 * @prop {boolean} favoritesOnly - 是否仅筛选已加入喜欢的藏书
 * @prop {ReadingStatus} [readingStatus='all'] - 当前选中的阅读状态（'all' | 'reading' | 'completed'）
 * @prop {boolean} [completedOnly=false] - 兼容历史布尔属性（当未显式传 readingStatus 时派生）
 * @prop {string} activeTag - 当前激活的分类标签名称（空表示全部标签）
 * @prop {Array<[string, number]>} tagCounts - 全库或当前来源前 18/30 高频标签及其计数
 * @prop {number} filteredCount - 当前筛选命中的条目数
 *
 * @emit toggleFavorites - 切换喜欢状态
 * @emit toggleCompleted - 切换已读状态（兼容事件）
 * @emit update:readingStatus - 阅读状态变更事件（'all' | 'reading' | 'completed'）
 * @emit selectTag - 选中指定标签（传空表示取消标签筛选）
 * @emit clearTag - 清空标签筛选
 */
import { computed, watch } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import AppChip from '@/components/AppChip.vue'
import SegmentedTabs, { type TabItem } from '@/components/SegmentedTabs.vue'
import type { ReadingStatus } from '@/types'

const trayExpanded = defineModel<boolean>('trayExpanded', { default: false })

export interface TagFilterBarProps {
  favoritesOnly: boolean
  readingStatus?: ReadingStatus
  completedOnly?: boolean
  activeTag: string
  /** [标签, 数量] 有序列表，按出现次数降序 */
  tagCounts: Array<[string, number]>
  /** 当前筛选命中的数量（用于提示文案） */
  filteredCount: number
}

const props = withDefaults(defineProps<TagFilterBarProps>(), {
  readingStatus: 'all',
  completedOnly: false,
})

const emit = defineEmits<{
  toggleFavorites: []
  toggleCompleted: []
  'update:readingStatus': [status: ReadingStatus]
  selectTag: [tag: string]
  clearTag: []
}>()

const readingStatusTabs: TabItem<ReadingStatus>[] = [
  { key: 'all', label: '全部' },
  { key: 'reading', label: '在读' },
  { key: 'completed', label: '已读' },
]

const effectiveReadingStatus = computed<ReadingStatus>(() => {
  if (props.readingStatus && props.readingStatus !== 'all') {
    return props.readingStatus
  }
  if (props.completedOnly) {
    return 'completed'
  }
  return props.readingStatus ?? 'all'
})

function onReadingStatusChange(status: ReadingStatus) {
  emit('update:readingStatus', status)
  if (status === 'completed' && !props.completedOnly) {
    emit('toggleCompleted')
  } else if (status !== 'completed' && props.completedOnly) {
    emit('toggleCompleted')
  }
}

/** 默认展示的高频标签数（连「全部」一起 ≤9 个 chip） */
const VISIBLE_TAGS = 8

const moreCount = computed(() => Math.max(0, props.tagCounts.length - VISIBLE_TAGS))
const primaryTags = computed(() => props.tagCounts.slice(0, VISIBLE_TAGS))
const overflowTags = computed(() => props.tagCounts.slice(VISIBLE_TAGS))

if (
  !trayExpanded.value &&
  props.activeTag &&
  overflowTags.value.some(([t]) => t === props.activeTag)
) {
  trayExpanded.value = true
}

watch(
  () => props.activeTag,
  (newTag) => {
    if (newTag && overflowTags.value.some(([t]) => t === newTag)) {
      trayExpanded.value = true
    }
  },
)

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
        :model-value="effectiveReadingStatus"
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

        <AppChip
          v-if="moreCount > 0"
          class="more-tags"
          :aria-expanded="trayExpanded"
          @click="trayExpanded = !trayExpanded"
        >
          <span>{{ trayExpanded ? '收起标签' : `更多 · ${moreCount}` }}</span>
          <template #suffix>
            <AppIcon
              name="chevron-down"
              size="xs"
              class="more-chevron"
              :class="{ 'is-rotated': trayExpanded }"
            />
          </template>
        </AppChip>
      </template>
    </div>

    <!-- 溢出标签平滑展开抽屉（CSS Grid 0fr ⇄ 1fr 尺寸插值） -->
    <div
      v-if="moreCount > 0"
      class="more-tags-tray"
      :class="{ 'is-expanded': trayExpanded }"
      :aria-hidden="!trayExpanded"
    >
      <div class="more-tags-inner">
        <div class="overflow-cluster cluster">
          <AppChip
            v-for="[tag, count] in overflowTags"
            :key="tag"
            :tabindex="trayExpanded ? 0 : -1"
            :pressed="activeTag === tag"
            :count="count"
            @click="selectTag(tag)"
          >
            {{ tag }}
          </AppChip>
        </div>
      </div>
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

.more-chevron {
  transition: transform var(--duration-2) var(--ease-spring);
}

.more-chevron.is-rotated {
  transform: rotate(180deg);
}

/* 溢出标签托盘：CSS Grid 0fr ⇄ 1fr 平滑尺寸插值 */
.more-tags-tray {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows var(--duration-2) var(--ease-out);
  overflow: clip;
}

.more-tags-tray.is-expanded {
  grid-template-rows: 1fr;
}

.more-tags-inner {
  min-height: 0;
  overflow: clip;
}

.overflow-cluster {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-top: var(--space-2);
  opacity: 0;
  transform: translateY(-4px);
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out);
}

.more-tags-tray.is-expanded .overflow-cluster {
  opacity: 1;
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  .more-tags-tray {
    transition: none !important;
  }

  .overflow-cluster {
    transition: none !important;
    transform: none !important;
  }

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

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'

/**
 * 书架标签筛选条 —— 「只看喜欢」+ 标签 chips + 当前筛选提示。
 * 选中状态 (activeTag / favoritesOnly) 由父级持有，本组件只回发事件。
 *
 * 漏斗式禁止（票据 03）：默认只渲染高频的前 8 个标签，其余收进
 * 「更多标签」展开按钮之下（再点收起），避免 ~20 个 chip 的墙造成
 * 决策点超载，也避免移动端出现无休止换行。
 */
const props = defineProps<{
  favoritesOnly: boolean
  activeTag: string
  /** [标签, 数量] 有序列表，按出现次数降序 */
  tagCounts: Array<[string, number]>
  /** 当前筛选命中的数量（用于提示文案） */
  filteredCount: number
}>()

const emit = defineEmits<{
  toggleFavorites: []
  selectTag: [tag: string]
  clearTag: []
}>()

/** 默认展示的高频标签数（连「全部」一起 ≤9 个 chip） */
const VISIBLE_TAGS = 8

const expanded = ref(false)
const moreCount = computed(() => Math.max(0, props.tagCounts.length - VISIBLE_TAGS))
const shownTags = computed(() =>
  expanded.value ? props.tagCounts : props.tagCounts.slice(0, VISIBLE_TAGS),
)

function selectTag(tag: string) {
  emit('selectTag', tag === props.activeTag ? '' : tag)
}

function clearFilter() {
  emit('selectTag', '')
}
</script>

<template>
  <div class="filter-toolbar">
    <div class="filter-cluster cluster" aria-label="书库筛选与标签">
      <button
        class="chip chip-button favorite-filter"
        type="button"
        :aria-pressed="favoritesOnly"
        @click="emit('toggleFavorites')"
      >
        <AppIcon class="heart-icon" :name="favoritesOnly ? 'heart-filled' : 'heart'" size="xs" />
        <span>只看喜欢</span>
      </button>

      <span v-if="tagCounts.length" class="filter-divider" aria-hidden="true" />

      <template v-if="tagCounts.length">
        <button
          class="chip chip-button"
          type="button"
          :aria-pressed="activeTag === ''"
          @click="clearFilter"
        >
          全部
        </button>
        <button
          v-for="[tag, count] in shownTags"
          :key="tag"
          class="chip chip-button"
          type="button"
          :aria-pressed="activeTag === tag"
          @click="selectTag(tag)"
        >
          {{ tag }} <small class="tag-count">{{ count }}</small>
        </button>

        <button
          v-if="moreCount > 0"
          class="chip chip-button more-tags"
          type="button"
          :aria-expanded="expanded"
          @click="expanded = !expanded"
        >
          {{ expanded ? '收起标签' : `更多 · ${moreCount}` }}
        </button>
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

.tag-count {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  opacity: 0.75;
}

.more-tags {
  font-family: var(--font-mono);
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

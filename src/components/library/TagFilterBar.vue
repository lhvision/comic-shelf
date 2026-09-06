<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import AppChip from '@/components/AppChip.vue'

/**
 * 书架标签筛选条 —— 「只看喜欢」+ 标签 chips + 当前筛选提示。
 * 选中状态 (activeTag / favoritesOnly) 由父级持有，本组件只回发事件。
 *
 * 漏斗式禁止（票据 03）：默认只渲染高频的前 8 个标签，其余收进
 * 「更多标签」展开按钮之下（再点收起），避免 ~20 个 chip 的墙造成
 * 决策点超载，也避免移动端出现无休止换行。
 */
const props = withDefaults(
  defineProps<{
    favoritesOnly: boolean
    completedOnly?: boolean
    activeTag: string
    /** [标签, 数量] 有序列表，按出现次数降序 */
    tagCounts: Array<[string, number]>
    /** 当前筛选命中的数量（用于提示文案） */
    filteredCount: number
  }>(),
  {
    completedOnly: false,
  },
)

const emit = defineEmits<{
  toggleFavorites: []
  toggleCompleted: []
  selectTag: [tag: string]
  clearTag: []
}>()

/** 默认展示的高频标签数（连「全部」一起 ≤9 个 chip） */
const VISIBLE_TAGS = 8

const moreCount = computed(() => Math.max(0, props.tagCounts.length - VISIBLE_TAGS))
const primaryTags = computed(() => props.tagCounts.slice(0, VISIBLE_TAGS))
const overflowTags = computed(() => props.tagCounts.slice(VISIBLE_TAGS))

const expanded = ref(
  Boolean(props.activeTag && overflowTags.value.some(([t]) => t === props.activeTag)),
)

watch(
  () => props.activeTag,
  (newTag) => {
    if (newTag && overflowTags.value.some(([t]) => t === newTag)) {
      expanded.value = true
    }
  },
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
      <AppChip class="favorite-filter" :pressed="favoritesOnly" @click="emit('toggleFavorites')">
        <template #prefix>
          <AppIcon class="heart-icon" :name="favoritesOnly ? 'heart-filled' : 'heart'" size="xs" />
        </template>
        <span>只看喜欢</span>
      </AppChip>

      <AppChip class="completed-filter" :pressed="completedOnly" @click="emit('toggleCompleted')">
        <template #prefix>
          <AppIcon class="archive-icon" name="archive" size="xs" />
        </template>
        <span>只看已读</span>
      </AppChip>

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
          :aria-expanded="expanded"
          @click="expanded = !expanded"
        >
          <span>{{ expanded ? '收起标签' : `更多 · ${moreCount}` }}</span>
          <template #suffix>
            <AppIcon
              name="chevron-down"
              size="xs"
              class="more-chevron"
              :class="{ 'is-rotated': expanded }"
            />
          </template>
        </AppChip>
      </template>
    </div>

    <!-- 溢出标签平滑展开抽屉（CSS Grid 0fr ⇄ 1fr 尺寸插值） -->
    <div
      v-if="moreCount > 0"
      class="more-tags-tray"
      :class="{ 'is-expanded': expanded }"
      :aria-hidden="!expanded"
    >
      <div class="more-tags-inner">
        <div class="overflow-cluster cluster">
          <AppChip
            v-for="[tag, count] in overflowTags"
            :key="tag"
            :tabindex="expanded ? 0 : -1"
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

.favorite-filter,
.completed-filter {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.completed-filter .archive-icon {
  width: 0.85rem;
  height: 0.85rem;
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

/* 溢出标签托盘：CSS Grid 轨道尺寸插值 */
.more-tags-tray {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows var(--duration-2) var(--ease-out);
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

<script setup lang="ts">
import { computed, ref } from 'vue'

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
  <div>
    <div class="tag-filter cluster" aria-label="筛选书库">
      <button
        class="chip chip-button favorite-filter"
        type="button"
        :aria-pressed="favoritesOnly"
        @click="emit('toggleFavorites')"
      >
        ♥ 只看喜欢
      </button>
    </div>

    <div v-if="tagCounts.length" class="tag-filter cluster" aria-label="按标签过滤">
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
        {{ tag }} <small>{{ count }}</small>
      </button>

      <button
        v-if="moreCount > 0"
        class="chip chip-button more-tags"
        type="button"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起标签' : `更多标签 · ${moreCount}` }}
      </button>
    </div>

    <p v-if="activeTag" class="filter-note">
      正在查看标签「{{ activeTag }}」的 {{ filteredCount }} 本
      <button type="button" @click="clearFilter">清除</button>
    </p>
  </div>
</template>

<style scoped>
.tag-filter {
  padding: var(--space-4) 0;
}

.filter-note {
  padding: var(--space-2) 0;
  color: var(--ink-1);
  font-size: var(--text-sm);
}

.filter-note button {
  margin-left: var(--space-3);
  background: transparent;
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 3px;
}
</style>

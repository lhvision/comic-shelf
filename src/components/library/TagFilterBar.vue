<script setup lang="ts">
/**
 * 书架标签筛选条 —— 「只看喜欢」+ 标签 chips + 当前筛选提示。
 * 选中状态 (activeTag / favoritesOnly) 由父级持有，本组件只回发事件。
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
        v-for="[tag, count] in tagCounts"
        :key="tag"
        class="chip chip-button"
        type="button"
        :aria-pressed="activeTag === tag"
        @click="selectTag(tag)"
      >
        {{ tag }} <small>{{ count }}</small>
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

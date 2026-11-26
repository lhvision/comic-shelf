<script setup lang="ts">
/**
 * ReaderPipSwitcherPanel.vue — 桌面悬浮阅览窗「选话目录 / 快捷换书」抽屉面板。
 * 支持多章节直选跳话，以及按标题 / 车号 / 作者检索并按在读优先排序的快捷换书。
 */
import { computed, ref, useTemplateRef, watch } from 'vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ReaderPipBookItem from '@/components/reader/pip/ReaderPipBookItem.vue'
import type { Chapter, LibrarySummary } from '@/types'
import { isCompletedComic, isInProgressComic } from '@/utils/is'

const MAX_SWITCHER_ITEMS = 30

const props = defineProps<{
  mode: 'chapters' | 'books'
  chapters: Chapter[]
  currentChapterId: string | null
  currentSource: string
  currentSourceId: string
  libraryItems: LibrarySummary[]
  hasChapters: boolean
  canSwitchBooks: boolean
}>()

defineEmits<{
  switchMode: [mode: 'chapters' | 'books']
  close: []
  selectChapter: [chapterId: string]
  selectComic: [source: string, sourceId: string]
}>()

const searchQuery = ref('')
const searchInputEl = useTemplateRef<HTMLInputElement>('searchInputEl')

const quickSwitchBooks = computed<LibrarySummary[]>(() => {
  if (!props.canSwitchBooks) return []
  const query = searchQuery.value.trim().toLocaleLowerCase()
  const filtered = props.libraryItems.filter((item) => {
    if (item.source === props.currentSource && item.source_id === props.currentSourceId) {
      return false
    }
    if (!query) return true
    const haystack = [item.title, item.display_id, ...(item.authors ?? [])]
      .join('\n')
      .toLocaleLowerCase()
    return haystack.includes(query)
  })

  const statusRank = (item: LibrarySummary) => {
    if (isInProgressComic(item)) return 0
    if (!isCompletedComic(item)) return 1
    return 2
  }

  return filtered
    .toSorted((a, b) => {
      const rankDiff = statusRank(a) - statusRank(b)
      if (rankDiff !== 0) return rankDiff
      const timeA = a.imported_at ? Date.parse(a.imported_at) || 0 : 0
      const timeB = b.imported_at ? Date.parse(b.imported_at) || 0 : 0
      return timeB - timeA
    })
    .slice(0, MAX_SWITCHER_ITEMS)
})

watch(
  () => props.mode,
  (mode) => {
    if (mode === 'books') {
      searchInputEl.value?.focus()
    }
  },
  { flush: 'post', immediate: true },
)

watch(
  () => `${props.currentSource}/${props.currentSourceId}`,
  () => {
    searchQuery.value = ''
  },
)
</script>

<template>
  <section
    class="pip-switcher-panel"
    :aria-label="mode === 'chapters' ? '本话章节目录' : '快捷切换藏书'"
  >
    <div class="pip-switcher-tabs">
      <div class="pip-switcher-tab-group">
        <button
          v-if="hasChapters"
          type="button"
          class="pip-tab-btn"
          :class="{ 'is-active': mode === 'chapters' }"
          @click="$emit('switchMode', 'chapters')"
        >
          本话目录 ({{ chapters.length }})
        </button>
        <button
          v-if="canSwitchBooks"
          type="button"
          class="pip-tab-btn"
          :class="{ 'is-active': mode === 'books' }"
          @click="$emit('switchMode', 'books')"
        >
          快捷换书
        </button>
      </div>
      <AppButton
        theme="reader"
        variant="ghost"
        size="xs"
        shape="circle"
        icon="close"
        aria-label="关闭切换面板"
        @click="$emit('close')"
      />
    </div>

    <div v-if="mode === 'chapters'" class="pip-switcher-list">
      <button
        v-for="ch in chapters"
        :key="ch.id"
        type="button"
        class="pip-chapter-item"
        :class="{ 'is-current': ch.id === currentChapterId }"
        @click="$emit('selectChapter', ch.id)"
      >
        <span class="pip-chapter-name">第 {{ ch.index }} 話 · {{ ch.title }}</span>
        <span class="pip-chapter-meta">
          {{ ch.id === currentChapterId ? '在看 · ' : '' }}{{ ch.page_count }}P
        </span>
      </button>
    </div>

    <div v-else class="pip-books-body">
      <label class="pip-search-box">
        <AppIcon name="search" size="xs" />
        <input
          ref="searchInputEl"
          v-model="searchQuery"
          type="search"
          class="pip-search-input"
          placeholder="搜标题 / 车号 / 作者…"
          aria-label="搜索书库藏书"
        />
      </label>

      <div class="pip-switcher-list">
        <ReaderPipBookItem
          v-for="item in quickSwitchBooks"
          :key="`${item.source}/${item.source_id}`"
          :item="item"
          @select="(src, sid) => $emit('selectComic', src, sid)"
        />
        <p v-if="quickSwitchBooks.length === 0" class="pip-empty-hint">未找到匹配的藏书</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.pip-switcher-panel {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--space-2, 0.5rem);
  padding: var(--space-2, 0.5rem);
  box-sizing: border-box;
}

.pip-switcher-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2, 0.5rem);
}

.pip-switcher-tab-group {
  display: flex;
  gap: var(--space-1, 0.25rem);
}

.pip-tab-btn {
  padding: var(--space-1, 0.25rem) var(--space-2-5, 0.625rem);
  border-radius: var(--radius-pill, 9999px);
  border: 1px solid var(--reader-line, rgb(238 231 218 / 14%));
  background: transparent;
  color: var(--reader-muted, #938d80);
  font-size: var(--text-xs, 0.75rem);
  cursor: pointer;
}

.pip-tab-btn.is-active {
  background: var(--reader-surface-strong, rgb(238 231 218 / 8%));
  color: var(--reader-ink, #eee7da);
  border-color: var(--reader-accent, #e87a58);
}

.pip-books-body {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--space-2, 0.5rem);
}

.pip-search-box {
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-1-5, 0.375rem) var(--space-2-5, 0.625rem);
  border-radius: var(--radius-2, 0.625rem);
  background: var(--reader-surface, rgb(238 231 218 / 4%));
  border: 1px solid var(--reader-line, rgb(238 231 218 / 14%));
  color: var(--reader-muted, #938d80);
}

.pip-search-input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--reader-ink, #eee7da);
  font-size: var(--text-xs, 0.75rem);
}

.pip-switcher-list {
  min-height: 0;
  overflow-y: auto;
  display: grid;
  align-content: start;
  gap: var(--space-1-5, 0.375rem);
  scrollbar-width: thin;
}

.pip-chapter-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2-5, 0.625rem);
  padding: var(--space-2, 0.5rem);
  border-radius: var(--radius-2, 0.625rem);
  border: 1px solid var(--reader-line-soft, rgb(238 231 218 / 10%));
  background: var(--reader-surface, rgb(238 231 218 / 4%));
  color: var(--reader-ink, #eee7da);
  text-align: left;
  cursor: pointer;
}

.pip-chapter-item:hover {
  background: var(--reader-surface-hover, rgb(238 231 218 / 14%));
}

.pip-chapter-item.is-current {
  border-color: var(--reader-accent, #e87a58);
}

.pip-chapter-name {
  min-width: 0;
  font-size: var(--text-xs, 0.75rem);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-chapter-meta {
  flex-shrink: 0;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
}

.pip-empty-hint {
  margin: var(--space-4, 1rem) 0;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

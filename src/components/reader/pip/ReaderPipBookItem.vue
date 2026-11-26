<script setup lang="ts">
/**
 * ReaderPipBookItem.vue — 桌面悬浮阅览窗通用书目条目卡片。
 * 复用于顶栏「快捷换书」抽屉与末页「全卷完 · 接卷推荐」列表。
 */
import { coverSrcset } from '@/api/client'
import type { LibrarySummary } from '@/types'
import { isCompletedComic, isInProgressComic } from '@/utils/is'

const props = withDefaults(
  defineProps<{
    item: LibrarySummary
    showAuthor?: boolean
  }>(),
  {
    showAuthor: false,
  },
)

defineEmits<{
  select: [source: string, sourceId: string]
}>()

function formatBookStatus(item: LibrarySummary): string {
  if (isCompletedComic(item)) return '已读完'
  if (isInProgressComic(item)) return `在读 ${item.last_page}/${item.page_count}P`
  return '未读'
}

function formatBookMeta(item: LibrarySummary, showAuthor: boolean): string {
  const status = formatBookStatus(item)
  return showAuthor
    ? `${status} · ${item.authors.join(' / ') || '佚名'}`
    : `${item.display_id} · ${status}`
}

function bookCoverSrcset(cover?: string): string | undefined {
  if (!cover) return undefined
  return coverSrcset(cover) || undefined
}
</script>

<template>
  <button
    type="button"
    class="pip-book-item"
    @click="$emit('select', props.item.source, props.item.source_id)"
  >
    <img
      v-if="props.item.cover_paths?.[0]"
      :src="props.item.cover_paths[0]"
      :srcset="bookCoverSrcset(props.item.cover_paths[0])"
      sizes="120px"
      :alt="props.item.title"
      class="pip-book-cover"
      loading="lazy"
      decoding="async"
    />
    <div v-else class="pip-book-cover is-empty">{{ props.item.display_id }}</div>
    <div class="pip-book-info">
      <strong class="pip-book-title">{{ props.item.title }}</strong>
      <span class="pip-book-meta">{{ formatBookMeta(props.item, props.showAuthor) }}</span>
    </div>
  </button>
</template>

<style scoped>
.pip-book-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-2-5, 0.625rem);
  padding: var(--space-2, 0.5rem);
  border-radius: var(--radius-2, 0.625rem);
  border: 1px solid var(--reader-line-soft, rgb(238 231 218 / 10%));
  background: var(--reader-surface, rgb(238 231 218 / 4%));
  color: var(--reader-ink, #eee7da);
  text-align: left;
  cursor: pointer;
}

.pip-book-item:hover {
  background: var(--reader-surface-hover, rgb(238 231 218 / 14%));
}

.pip-book-cover {
  width: 2.25rem;
  height: 3rem;
  object-fit: cover;
  border-radius: var(--radius-1, 0.375rem);
  flex-shrink: 0;
  background: var(--reader-bg, #0d0e0c);
}

.pip-book-cover.is-empty {
  display: grid;
  place-items: center;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
}

.pip-book-info {
  min-width: 0;
  display: grid;
  gap: var(--space-0-5, 0.125rem);
}

.pip-book-title {
  font-size: var(--text-xs, 0.75rem);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-book-meta {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption, 0.6875rem);
  color: var(--reader-muted, #938d80);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

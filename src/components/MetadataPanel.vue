<script setup lang="ts">
import { computed } from 'vue'
import { useToggle } from '@vueuse/core'
import type { ComicMeta } from '@/types'
import AppTextClamp from '@/components/AppTextClamp.vue'
import AppChip from '@/components/AppChip.vue'

const props = defineProps<{
  meta: ComicMeta
}>()

const [descExpanded, toggleDesc] = useToggle(false)
const hasLongDescription = computed(() => {
  const desc = props.meta.description || ''
  return desc.length > 90 || desc.includes('\n')
})

const fieldRows = [
  { label: '禁漫车', value: props.meta.display_id, mono: true },
  { label: '作品', value: props.meta.works.join(' / ') || '—' },
  { label: '登场人物', value: props.meta.actors.join(' / ') || '—' },
  { label: '作者', value: props.meta.authors.join(' / ') || '佚名' },
  { label: '上传者', value: props.meta.uploader || '未返回' },
  { label: '页数', value: props.meta.page_count ? `${props.meta.page_count} P` : '—' },
  {
    label: '章节',
    value: (props.meta.chapters?.length ?? 0) > 1 ? `共 ${props.meta.chapters!.length} 话` : '单话',
    mono: true,
  },
  { label: '上架日期', value: props.meta.published_at || '—', mono: true },
  { label: '更新日期', value: props.meta.updated_at || '—', mono: true },
  {
    label: '观看 / 喜欢',
    value: `${props.meta.views || '—'} 次观看 · ${props.meta.likes || '—'} 点击喜欢`,
  },
]
</script>

<template>
  <section class="metadata-panel" aria-labelledby="meta-title">
    <div class="meta-head">
      <div class="meta-head-top">
        <p class="eyebrow">Catalog card</p>
        <span class="meta-id" :title="meta.display_id">{{ meta.display_id }}</span>
      </div>
      <AppTextClamp
        id="meta-title"
        as="h2"
        :lines="2"
        :text="meta.title"
        tooltip-side="bottom"
        tooltip-width="30rem"
      />
    </div>

    <dl class="meta-grid">
      <div v-for="(row, idx) in fieldRows" :key="row.label" class="meta-row">
        <dt>{{ row.label }}</dt>
        <dd :data-mono="row.mono">
          <AppTextClamp
            as="span"
            :lines="2"
            :text="row.value"
            :mono="row.mono"
            tooltip-side="top"
            :tooltip-align="idx % 2 === 1 ? 'end' : 'start'"
            tooltip-width="26rem"
          />
        </dd>
      </div>
    </dl>

    <div class="meta-block">
      <h3>分类标签</h3>
      <div class="cluster">
        <AppChip v-for="tag in meta.tags" :key="tag">{{ tag }}</AppChip>
        <span v-if="meta.tags.length === 0" class="muted">无标签</span>
      </div>
    </div>

    <div class="meta-block">
      <div class="meta-block-header">
        <h3>叙述</h3>
        <button
          v-if="hasLongDescription"
          type="button"
          class="desc-toggle-btn"
          @click="toggleDesc()"
        >
          {{ descExpanded ? '收起 ▴' : '展开全文 ▾' }}
        </button>
      </div>
      <p class="description" :class="{ 'line-clamp-3': !descExpanded && hasLongDescription }">
        {{ meta.description || '原页面没有填写叙述。' }}
      </p>
    </div>

    <p v-if="meta.source_url" class="source-link">
      来源：
      <a :href="meta.source_url" target="_blank" rel="noreferrer noopener">
        {{ meta.source_url }}
      </a>
    </p>
  </section>
</template>

<style scoped>
.metadata-panel {
  display: grid;
  gap: var(--space-5);
}

.meta-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.meta-head-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.meta-head-top .eyebrow {
  margin: 0;
  font-size: var(--text-caption);
  letter-spacing: 0.12em;
  color: var(--accent);
  text-transform: uppercase;
}

.meta-head h2,
.meta-head :deep(h2) {
  margin: 0;
  font-size: var(--text-xl);
  line-height: var(--leading-tight);
  letter-spacing: -0.01em;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.meta-id {
  padding: 0.25rem 0.55rem;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent-strong);
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

@supports (text-fit: shrink) {
  .meta-id {
    text-fit: shrink;
  }
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-block: 1px solid var(--line);
}

.meta-row {
  display: grid;
  grid-template-columns: minmax(4.8rem, 0.45fr) 1fr;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--line);
}

.meta-row:nth-child(odd) {
  padding-right: var(--space-4);
}

.meta-row:nth-child(even) {
  padding-left: var(--space-4);
  border-left: 1px solid var(--line);
}

.meta-row:last-child {
  border-bottom: 0;
}

.meta-row dt {
  color: var(--ink-2);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.06em;
}

.meta-row dd {
  min-width: 0;
  font-size: var(--text-sm);
  overflow-wrap: anywhere;
}

.meta-row dd[data-mono='true'] {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.meta-block h3 {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--ink-2);
  margin-bottom: var(--space-2);
}

.meta-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.meta-block-header h3 {
  margin-bottom: 0;
}

.desc-toggle-btn {
  background: none;
  border: none;
  padding: var(--space-0-5) var(--space-1);
  font-family: var(--font-body);
  font-size: var(--text-xs);
  color: var(--accent);
  cursor: pointer;
  border-radius: var(--radius-1);
  transition:
    color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.desc-toggle-btn:hover {
  color: var(--accent-strong);
  background-color: var(--accent-soft);
}

.desc-toggle-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.description,
:deep(.description) {
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 50%, transparent);
  color: var(--ink-1);
  font-size: var(--text-sm);
  white-space: pre-line;
}

.muted {
  color: var(--ink-2);
  font-size: var(--text-sm);
}

.source-link {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  overflow-wrap: anywhere;
}

.source-link a {
  color: var(--accent-strong);
  text-decoration: underline;
  text-underline-offset: 3px;
}

@media (max-width: 640px) {
  .meta-grid {
    grid-template-columns: 1fr;
  }

  .meta-row:nth-child(odd),
  .meta-row:nth-child(even) {
    padding-inline: 0;
    border-left: 0;
  }
}
</style>

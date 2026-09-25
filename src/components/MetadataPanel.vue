<script setup lang="ts">
import { computed, watch } from 'vue'
import { useToggle } from '@vueuse/core'
import type { ComicMeta } from '@/types'
import AppIcon from '@/components/AppIcon.vue'
import AppTextClamp from '@/components/AppTextClamp.vue'
import AppChip from '@/components/AppChip.vue'
import { getSourceIdLabel } from '@/utils/source'

const props = defineProps<{
  meta: ComicMeta
}>()

const [descExpanded, toggleDesc] = useToggle(false)
const hasLongDescription = computed(() => {
  const desc = props.meta.description || ''
  return desc.split('\n').length > 3 || desc.length > 90
})

// 跨作品路由复用时自动复位叙述折叠状态
watch(
  () => props.meta.display_id,
  () => {
    descExpanded.value = false
  },
)

const fieldRows = computed(() => {
  const idLabel = getSourceIdLabel(props.meta.source)
  const rows = [
    { label: idLabel, value: props.meta.display_id, mono: true },
    { label: '作品', value: props.meta.works.join(' / ') || '—' },
    { label: '登场人物', value: props.meta.actors.join(' / ') || '—' },
    { label: '作者', value: props.meta.authors.join(' / ') || '佚名' },
    { label: '上传者', value: props.meta.uploader || '未返回' },
    { label: '页数', value: props.meta.page_count ? `${props.meta.page_count} P` : '—' },
    {
      label: '章节',
      value:
        (props.meta.chapters?.length ?? 0) > 1 ? `共 ${props.meta.chapters!.length} 话` : '单话',
      mono: true,
    },
    { label: '上架日期', value: props.meta.published_at || '—', mono: true },
    { label: '更新日期', value: props.meta.updated_at || '—', mono: true },
  ]
  if (props.meta.source !== 'local') {
    rows.push({
      label: '观看 / 喜欢',
      value: `${props.meta.views || '—'} 次观看 · ${props.meta.likes || '—'} 点击喜欢`,
    })
  }
  if (props.meta.custom_pages) {
    rows.push({
      label: '装订状态',
      value: '馆长重新装订（保护生效中）',
      mono: false,
    })
  }
  if (isMultiRemote.value) {
    rows.push({
      label: '追更状态',
      value: autoUpdateLabel.value,
      mono: false,
    })
  }
  return rows
})

const isMultiRemote = computed(() => {
  return (props.meta.chapters?.length ?? 0) > 1 && props.meta.source !== 'local'
})

const isHiatus = computed(() => {
  if (!isMultiRemote.value) return false
  const dateStr = props.meta.updated_at || props.meta.published_at || props.meta.imported_at
  if (!dateStr || !dateStr.trim()) return false
  const parsed = Date.parse(dateStr.replace(' ', 'T'))
  if (Number.isNaN(parsed)) return false
  return Date.now() - parsed > 30 * 86400 * 1000
})

const autoUpdateLabel = computed(() => {
  if (!isMultiRemote.value) return ''
  if (props.meta.custom_pages) return '已重新装订保护（跳过远端追更）'
  if (isHiatus.value) return '超过 1 个月未更新（已暂停巡检）'
  const interval = props.meta.auto_update_interval_days ?? 15
  if (interval === 0) return '已关闭自动巡检'
  return `自动追更中（每 ${interval} 天巡检）`
})
</script>

<template>
  <section class="metadata-panel" aria-labelledby="meta-title">
    <div class="meta-head">
      <div class="meta-head-top">
        <span class="meta-id" :title="meta.display_id">{{ meta.display_id }}</span>
        <span
          v-if="meta.custom_pages"
          class="custom-pages-badge"
          title="画卷已由馆长重新装订，已开启远端覆盖保护"
        >
          重新装订
        </span>
        <span
          v-if="isMultiRemote && isHiatus"
          class="hiatus-badge"
          title="作品已超过 1 个月未更新，自动巡检已暂停。如需更新请在操作栏点击“刷新资料”。"
        >
          已断更
        </span>
        <span
          v-else-if="
            isMultiRemote && !meta.custom_pages && (meta.auto_update_interval_days ?? 15) > 0
          "
          class="auto-update-badge"
          :title="`多章节连载作品，每 ${meta.auto_update_interval_days ?? 15} 天自动巡检追更`"
        >
          追更中
        </span>
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
          :aria-expanded="descExpanded"
          aria-controls="meta-description"
          @click="toggleDesc()"
        >
          <span>{{ descExpanded ? '收起' : '展开全文' }}</span>
          <AppIcon
            name="chevron-down"
            size="xs"
            class="desc-chevron"
            :class="{ 'is-rotated': descExpanded }"
          />
        </button>
      </div>
      <div class="description">
        <p
          id="meta-description"
          class="description-content"
          :class="{
            'is-clamped': !descExpanded && hasLongDescription,
            'is-expanded': descExpanded && hasLongDescription,
          }"
        >
          {{ meta.description || '原页面没有填写叙述。' }}
        </p>
      </div>
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

.meta-head-top {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.meta-id {
  padding: var(--space-1) var(--space-2);
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

.custom-pages-badge {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--accent);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent);
  background: var(--accent-soft);
  white-space: nowrap;
}

.hiatus-badge {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  background: var(--paper-2);
  white-space: nowrap;
}

.auto-update-badge {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--accent);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent);
  background: var(--accent-soft);
  white-space: nowrap;
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

/* 现代渐进增强轨：CSS Gap Decorations (Chrome 149+) 原生网格装饰线体系 */
@supports (row-rule: 1px solid red) {
  .meta-grid {
    column-gap: var(--space-8);
    column-rule: 1px solid var(--line);
    row-rule: 1px solid var(--line);
    column-rule-visibility-items: between;
  }

  .meta-row {
    border-bottom: 0;
  }

  .meta-row:nth-child(odd),
  .meta-row:nth-child(even) {
    padding-inline: 0;
    border-left: 0;
  }
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
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
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

.desc-chevron {
  transition: transform var(--duration-2) var(--ease-spring);
}

.desc-chevron.is-rotated {
  transform: rotate(180deg);
}

.description,
:deep(.description) {
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 50%, transparent);
  color: var(--ink-1);
  font-size: var(--text-sm);
  line-height: var(--leading-body);
}

.description-content {
  margin: 0;
  line-height: var(--leading-body);
  white-space: pre-line;
  overflow: clip;
  interpolate-size: allow-keywords;
  transition: height var(--duration-2) var(--ease-out);
}

.description-content.is-clamped {
  height: calc(3 * var(--leading-body) * 1em);
  height: 3lh;
  -webkit-mask-image: linear-gradient(to bottom, black calc(100% - 1.2lh), transparent 100%);
  mask-image: linear-gradient(to bottom, black calc(100% - 1.2lh), transparent 100%);
}

.description-content.is-expanded {
  height: auto;
  -webkit-mask-image: none;
  mask-image: none;
}

@media (prefers-reduced-motion: reduce) {
  .description-content {
    transition: none !important;
  }

  .desc-chevron {
    transition: none !important;
  }
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

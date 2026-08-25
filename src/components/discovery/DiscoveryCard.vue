<script setup lang="ts">
import { computed } from 'vue'
import AppButton from '@/components/AppButton.vue'
import type { DiscoveryItem } from '@/types'

const props = defineProps<{
  item: DiscoveryItem
  rank: number
  ingesting?: boolean
}>()

const emit = defineEmits<{
  ingest: [item: DiscoveryItem]
}>()

const rankFormatted = computed(() => String(props.rank).padStart(2, '0'))
const isTopThree = computed(() => props.rank <= 3)
const libraryRoute = computed(() => `/comic/${props.item.source}/${props.item.source_id}`)
</script>

<template>
  <article class="discovery-card" :class="{ 'in-library': item.in_library }">
    <div class="card-cover-wrapper">
      <a
        v-if="item.url"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer"
        class="cover-visual cover-link"
        :title="`在禁漫原站查看《${item.title}》`"
      >
        <div class="cover-placeholder">
          <span class="cover-pattern-id">{{ item.id }}</span>
          <span v-if="item.category" class="cover-category-pill">{{ item.category }}</span>
          <span class="cover-hint">
            <span>原站预览</span>
            <svg
              viewBox="0 0 24 24"
              width="11"
              height="11"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"
              />
            </svg>
          </span>
        </div>
      </a>
      <div v-else class="cover-visual">
        <div class="cover-placeholder">
          <span class="cover-pattern-id">{{ item.id }}</span>
          <span v-if="item.category" class="cover-category-pill">{{ item.category }}</span>
        </div>
      </div>

      <div class="rank-stamp" :class="{ 'rank-top': isTopThree }">
        <span class="rank-hash">#</span>{{ rankFormatted }}
      </div>

      <a
        v-if="item.url"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer"
        class="source-stamp"
        title="在禁漫原站打开"
      >
        <span>JM ↗</span>
      </a>
      <span v-else class="id-stamp">{{ item.id }}</span>
    </div>

    <div class="card-body">
      <h2 class="card-title line-clamp-2" :title="item.title">
        <a
          v-if="item.url"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          class="title-link"
        >
          {{ item.title }}
        </a>
        <template v-else>
          {{ item.title }}
        </template>
      </h2>
      <p class="card-author">{{ item.author || '佚名' }}</p>

      <div class="card-action-bar">
        <RouterLink
          v-if="item.in_library"
          :to="libraryRoute"
          class="btn btn-success btn-sm btn-block in-library-btn"
        >
          <span class="status-dot"></span>
          已在书架 · 详情
        </RouterLink>

        <AppButton
          v-else
          variant="soft"
          size="sm"
          block
          :loading="ingesting"
          @click="emit('ingest', item)"
        >
          + 一键收录
        </AppButton>
      </div>
    </div>
  </article>
</template>

<style scoped>
.discovery-card {
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-2);
  border: 1px solid var(--line);
  background: var(--paper-0);
  box-shadow: var(--shadow-1);
  overflow: hidden;
  transition:
    transform var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out),
    border-color var(--duration-1) var(--ease-out);
}

.discovery-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
  border-color: color-mix(in oklab, var(--accent) 30%, var(--line));
}

.card-cover-wrapper {
  position: relative;
  aspect-ratio: 3 / 4.15;
  background: var(--paper-1);
  overflow: hidden;
}

.cover-visual {
  width: 100%;
  height: 100%;
  display: block;
  text-decoration: none;
}

.cover-link {
  cursor: pointer;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  background:
    radial-gradient(
      circle at top right,
      color-mix(in oklab, var(--accent-soft) 80%, transparent) 0%,
      transparent 60%
    ),
    linear-gradient(145deg, var(--paper-1) 0%, var(--paper-2) 100%);
  color: var(--ink-2);
  padding: var(--space-3);
  text-align: center;
  transition: background var(--duration-2) var(--ease-out);
}

.cover-link:hover .cover-placeholder {
  background:
    radial-gradient(
      circle at top right,
      color-mix(in oklab, var(--accent) 25%, transparent) 0%,
      transparent 70%
    ),
    linear-gradient(145deg, var(--paper-1) 0%, var(--paper-2) 100%);
}

.cover-pattern-id {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  letter-spacing: 0.1em;
  color: var(--ink-1);
  opacity: 0.75;
}

.cover-category-pill {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  background: var(--paper-0);
  border: 1px solid var(--line);
  font-size: var(--text-caption);
  color: var(--ink-1);
}

.cover-hint {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: var(--space-1);
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--paper-0) 80%, transparent);
  border: 1px dashed color-mix(in oklab, var(--accent) 50%, var(--line));
  font-size: var(--text-caption);
  color: var(--accent-strong);
  font-weight: 500;
  opacity: 0.85;
  transition:
    opacity var(--duration-1) var(--ease-out),
    transform var(--duration-1) var(--ease-out);
}

.cover-link:hover .cover-hint {
  opacity: 1;
  transform: translateY(-1px);
}

.rank-stamp {
  position: absolute;
  top: var(--space-2);
  left: var(--space-2);
  padding: 0.125rem 0.4rem;
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-weight: 700;
  letter-spacing: 0.04em;
  background: color-mix(in oklab, var(--paper-0) 90%, transparent);
  color: var(--ink-1);
  border: 1px solid var(--line);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  gap: 0.1rem;
}

.rank-top {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent-strong);
  box-shadow: 0 2px 6px color-mix(in oklab, var(--accent) 40%, transparent);
}

.rank-hash {
  opacity: 0.75;
  font-size: 0.75em;
}

.source-stamp,
.id-stamp {
  position: absolute;
  bottom: var(--space-2);
  right: var(--space-2);
  padding: 0.125rem 0.375rem;
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-1);
  background: color-mix(in oklab, var(--paper-0) 85%, transparent);
  border: 1px solid var(--line);
  text-decoration: none;
  transition: all var(--duration-1) var(--ease-out);
}

.source-stamp:hover {
  background: var(--paper-0);
  color: var(--accent);
  border-color: var(--accent);
}

.card-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: var(--space-3);
  gap: var(--space-2);
}

.card-title {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 600;
  line-height: 1.35;
  color: var(--ink-0);
  margin: 0;
  min-height: 2.7em;
}

.title-link {
  color: inherit;
  text-decoration: none;
  transition: color var(--duration-1) var(--ease-out);
}

.title-link:hover {
  color: var(--accent);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
}

.card-author {
  font-size: var(--text-caption);
  color: var(--ink-2);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-action-bar {
  margin-top: auto;
  padding-top: var(--space-2);
}

.in-library-btn {
  font-weight: 600;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
</style>

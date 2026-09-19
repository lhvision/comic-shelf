<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppTextClamp from '@/components/AppTextClamp.vue'
import AppChip from '@/components/AppChip.vue'
import type { DiscoveryItem } from '@/types'
import { getSourceBadge, getSourceShortName } from '@/utils/source'
import { discoveryCoverUrl } from '@/api/modules/discovery'

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

// Scheme A: On-demand cover viewing (not loaded by default; purely opt-in)
const showCover = ref(false)
const coverLoading = ref(false)
const coverError = ref(false)
const retryKey = ref(0)

const hasCover = computed(() => Boolean(props.item.cover_url))

const coverUrl = computed(() => {
  if (!props.item.cover_url) return ''
  const base = discoveryCoverUrl(props.item.source, props.item.source_id, props.item.cover_url)
  return retryKey.value > 0 ? `${base}&_t=${retryKey.value}` : base
})

watch(
  () => props.item.id,
  () => {
    showCover.value = false
    coverLoading.value = false
    coverError.value = false
    retryKey.value = 0
  },
)

function toggleCover() {
  if (showCover.value) {
    showCover.value = false
    coverLoading.value = false
    coverError.value = false
  } else {
    showCover.value = true
    coverLoading.value = true
    coverError.value = false
  }
}

function onCoverLoaded() {
  coverLoading.value = false
  coverError.value = false
}

function onCoverError() {
  coverLoading.value = false
  coverError.value = true
}

function retryCover() {
  coverError.value = false
  coverLoading.value = true
  retryKey.value += 1
}
</script>

<template>
  <article class="discovery-card" :class="{ 'in-library': item.in_library }">
    <div class="card-cover-wrapper">
      <!-- When cover viewing is active -->
      <template v-if="showCover">
        <a
          v-if="item.url"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          class="cover-visual cover-link cover-image-wrap"
          :title="`在${getSourceShortName(item.source)}原站查看《${item.title}》`"
        >
          <img
            :src="coverUrl"
            :alt="item.title"
            class="cover-img"
            :class="{ 'is-loaded': !coverLoading && !coverError }"
            loading="lazy"
            @load="onCoverLoaded"
            @error="onCoverError"
          />
        </a>
        <div v-else class="cover-visual cover-image-wrap">
          <img
            :src="coverUrl"
            :alt="item.title"
            class="cover-img"
            :class="{ 'is-loaded': !coverLoading && !coverError }"
            loading="lazy"
            @load="onCoverLoaded"
            @error="onCoverError"
          />
        </div>

        <!-- Skeleton placeholder while loading -->
        <div v-if="coverLoading" class="cover-loading-overlay">
          <AppIcon name="refresh" size="sm" class="loading-spinner" />
          <span class="loading-label">加载封面中...</span>
        </div>

        <!-- Error state -->
        <div v-if="coverError" class="cover-error-overlay">
          <AppIcon name="info" size="xs" />
          <span>封面加载失败</span>
          <button type="button" class="cover-retry-btn" @click.stop.prevent="retryCover">
            重试
          </button>
        </div>

        <!-- Hide cover button (toggle off) -->
        <button
          type="button"
          class="cover-toggle-overlay-btn"
          title="收起封面"
          @click.stop.prevent="toggleCover"
        >
          <AppIcon name="eye-off" size="xs" />
          <span>收起封面</span>
        </button>
      </template>

      <!-- When cover viewing is inactive (default placeholder) -->
      <template v-else>
        <a
          v-if="item.url"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          class="cover-visual cover-link"
          :title="`在${getSourceShortName(item.source)}原站查看《${item.title}》`"
        >
          <div class="cover-placeholder">
            <span class="cover-pattern-id">{{ item.id }}</span>
            <AppChip v-if="item.category" size="sm" class="cover-category-pill">{{
              item.category
            }}</AppChip>
            <span class="cover-hint">
              <span>原站预览</span>
              <AppIcon name="external-link" size="xs" />
            </span>
          </div>
        </a>
        <div v-else class="cover-visual">
          <div class="cover-placeholder">
            <span class="cover-pattern-id">{{ item.id }}</span>
            <AppChip v-if="item.category" size="sm" class="cover-category-pill">{{
              item.category
            }}</AppChip>
          </div>
        </div>

        <!-- On-demand view cover trigger button -->
        <button
          v-if="hasCover"
          type="button"
          class="cover-action-trigger"
          title="查看封面图片"
          @click.stop.prevent="toggleCover"
        >
          <AppIcon name="eye" size="xs" />
          <span>查看封面</span>
        </button>
      </template>

      <div class="rank-stamp" :class="{ 'rank-top': isTopThree }">
        <span class="rank-hash">#</span>{{ rankFormatted }}
      </div>

      <a
        v-if="item.url"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer"
        class="source-stamp"
        :title="`在${getSourceShortName(item.source)}原站打开`"
      >
        <span>{{ getSourceBadge(item.source) }}</span>
        <AppIcon name="external-link" size="xs" />
      </a>
      <span v-else class="id-stamp">{{ item.id }}</span>
    </div>

    <div class="card-body">
      <AppTextClamp
        as="h2"
        class="card-title"
        :lines="2"
        :text="item.title"
        :delay="350"
        tooltip-side="top"
        tooltip-width="22rem"
      >
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
      </AppTextClamp>
      <AppTextClamp
        as="p"
        class="card-author"
        :lines="1"
        :text="item.author || '佚名'"
        tooltip-side="bottom"
        tooltip-width="20rem"
      />

      <div class="card-action-bar">
        <AppButton
          v-if="item.in_library"
          :to="libraryRoute"
          variant="success"
          size="sm"
          block
          class="in-library-btn"
        >
          <template #prefix>
            <span class="status-dot"></span>
          </template>
          已在书架 · 详情
        </AppButton>

        <AppButton
          v-else
          variant="soft"
          size="sm"
          block
          icon="plus"
          :loading="ingesting"
          @click="emit('ingest', item)"
        >
          一键收录
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
  --card-glow-color: color-mix(in oklab, var(--accent-soft) 80%, transparent);
  --card-glow-size: 60%;
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
      var(--card-glow-color) 0%,
      transparent var(--card-glow-size)
    ),
    linear-gradient(145deg, var(--paper-1) 0%, var(--paper-2) 100%);
  color: var(--ink-2);
  padding: var(--space-3);
  text-align: center;
  transition:
    --card-glow-color var(--duration-2) var(--ease-out),
    --card-glow-size var(--duration-2) var(--ease-out);
}

.cover-link:hover .cover-placeholder {
  --card-glow-color: color-mix(in oklab, var(--accent) 25%, transparent);
  --card-glow-size: 70%;
}

.cover-pattern-id {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  letter-spacing: 0.1em;
  color: var(--ink-1);
  opacity: 0.75;
}

.cover-category-pill {
  background: var(--paper-0);
}

.cover-hint {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  padding: var(--space-badge-y) var(--space-badge-x);
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
  padding: var(--space-0-5) var(--space-1);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-weight: 700;
  letter-spacing: 0.04em;
  background: color-mix(in oklab, var(--paper-0) 92%, transparent);
  color: var(--ink-1);
  border: 1px solid var(--line);
  box-shadow: 0 1px 3px rgb(0 0 0 / 18%);
  display: flex;
  align-items: center;
  gap: var(--space-0-5);
}

.rank-top {
  background: var(--accent);
  color: var(--accent-contrast);
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
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-0-5) var(--space-1);
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
  width: var(--space-1-5);
  height: var(--space-1-5);
  border-radius: 50%;
  background: currentColor;
}

.cover-action-trigger {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-0-5) var(--space-1-5);
  border-radius: var(--radius-1);
  font-size: var(--text-caption);
  font-weight: 500;
  color: var(--ink-1);
  background: color-mix(in oklab, var(--paper-0) 92%, transparent);
  border: 1px solid var(--line);
  box-shadow: 0 1px 3px rgb(0 0 0 / 12%);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
  z-index: 2;
}

.cover-action-trigger:hover {
  background: var(--paper-0);
  color: var(--accent-strong);
  border-color: color-mix(in oklab, var(--accent) 50%, var(--line));
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgb(0 0 0 / 18%);
}

.cover-toggle-overlay-btn {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-0-5) var(--space-1-5);
  border-radius: var(--radius-1);
  font-size: var(--text-caption);
  font-weight: 500;
  color: #ffffff;
  background: rgb(0 0 0 / 65%);
  backdrop-filter: blur(4px);
  border: 1px solid rgb(255 255 255 / 20%);
  box-shadow: 0 2px 4px rgb(0 0 0 / 25%);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
  z-index: 2;
}

.cover-toggle-overlay-btn:hover {
  background: rgb(0 0 0 / 85%);
  color: var(--accent-contrast);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.cover-image-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  display: block;
  background: var(--paper-2);
  overflow: hidden;
}

.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out);
}

.cover-img.is-loaded {
  opacity: 1;
}

.cover-link:hover .cover-img {
  transform: scale(1.03);
}

.cover-loading-overlay,
.cover-error-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1-5);
  background: var(--paper-1);
  color: var(--ink-2);
  font-size: var(--text-caption);
  z-index: 1;
}

.cover-error-overlay {
  color: var(--danger);
  background: color-mix(in oklab, var(--paper-1) 95%, var(--danger));
}

.loading-spinner {
  animation: spin 1s linear infinite;
  color: var(--accent);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.loading-label {
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.cover-retry-btn {
  margin-top: var(--space-1);
  padding: var(--space-0-5) var(--space-2);
  font-size: var(--text-caption);
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: var(--paper-0);
  color: var(--ink-0);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.cover-retry-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
</style>

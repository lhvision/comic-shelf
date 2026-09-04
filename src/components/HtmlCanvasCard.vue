<script setup lang="ts">
import { computed } from 'vue'
import type { LibrarySummary } from '@/types'
import HtmlCanvasSurface from '@/components/HtmlCanvasSurface.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import CacheProgress from '@/components/CacheProgress.vue'
import { useAuth } from '@/composables/useAuth'
import { api, coverSrcset } from '@/api/client'

const props = withDefaults(
  defineProps<{
    comic: LibrarySummary
    enabled?: boolean
    /** 实时缓存进度（后台任务运行时更新），优先于 comic.cached_pages */
    cache?: { running: boolean; cached: number; total: number }
  }>(),
  { enabled: false, cache: undefined },
)

const emit = defineEmits<{
  favoriteToggled: [source: string, sourceId: string, favorite: boolean]
}>()

const { authenticated } = useAuth()

const route = computed(() => `/comic/${props.comic.source}/${props.comic.source_id}`)
const primaryTags = computed(() => props.comic.tags.slice(0, 3))

const liveCached = computed(() => props.cache?.cached ?? props.comic.cached_pages)
const liveTotal = computed(() => props.cache?.total || props.comic.page_count)
const liveRunning = computed(() => Boolean(props.cache?.running))
const isCompleted = computed(
  () => (props.comic.last_page ?? 0) >= props.comic.page_count && props.comic.page_count > 0,
)
const isInProgress = computed(() => !isCompleted.value && (props.comic.last_page ?? 0) > 0)

// Force the canvas surface to re-paint whenever live progress or read status changes.
const redrawKey = computed(
  () => `${liveRunning.value}-${liveCached.value}/${liveTotal.value}-${isCompleted.value}`,
)
const cardTransitionName = computed(
  () => `card-${props.comic.source}-${props.comic.source_id.replace(/[^a-zA-Z0-9_-]/g, '_')}`,
)

function prefetch() {
  void import('@/views/ComicDetailView.vue').catch(() => {})
  void api.detail(props.comic.source, props.comic.source_id).catch(() => {})
}
</script>

<template>
  <HtmlCanvasSurface
    class="canvas-card"
    :style="{ viewTransitionName: cardTransitionName }"
    :enabled="enabled"
    :surface="`library-card:${comic.display_id}`"
    :redraw-key="redrawKey"
    @pointerenter.once="prefetch"
    @focusin.once="prefetch"
    @touchstart.passive.once="prefetch"
  >
    <!-- Complete DOM subtree: cover, title, meta, tags, views, cache progress. -->
    <article class="card-visual" :data-completed="isCompleted">
      <div class="cover">
        <img
          v-if="comic.cover_paths[0]"
          :src="comic.cover_paths[0]"
          :srcset="coverSrcset(comic.cover_paths[0])"
          sizes="(max-width: 680px) calc(50vw - 1.5rem), (max-width: 1200px) 25vw, 240px"
          :alt="`${comic.title} 封面`"
          loading="lazy"
          decoding="async"
        />
        <div v-else class="cover-empty">{{ comic.display_id }}</div>
        <span v-if="isCompleted" class="reading-stamp is-completed"> 已读完 </span>
        <span v-else-if="isInProgress" class="reading-stamp is-reading">
          {{ comic.last_page }}P / {{ comic.page_count }}P
        </span>
        <span class="id-stamp">{{ comic.display_id }}</span>
      </div>

      <div class="body">
        <h2 class="title line-clamp-2">{{ comic.title }}</h2>
        <p class="meta">{{ comic.authors.join(' / ') || '佚名' }} · {{ comic.page_count }}P</p>
        <div v-if="primaryTags.length" class="tags">
          <span v-for="tag in primaryTags" :key="tag" class="chip">{{ tag }}</span>
        </div>
        <div class="foot">
          <span>{{ comic.views }} 次观看</span>
          <CacheProgress :cached="liveCached" :total="liveTotal" :running="liveRunning" />
        </div>
      </div>
    </article>

    <template #overlay>
      <RouterLink :to="route" class="hitbox" :aria-label="comic.title" />
      <FavoriteButton
        :source="comic.source"
        :source-id="comic.source_id"
        :favorite="comic.favorite"
        :interactive="authenticated"
        @toggled="(value) => emit('favoriteToggled', comic.source, comic.source_id, value)"
      />
    </template>
  </HtmlCanvasSurface>
</template>

<style scoped>
.canvas-card {
  height: 100%;
  border-radius: var(--radius-3);
  border: 1px solid var(--line);
  background: color-mix(in oklab, var(--paper-0) 74%, var(--paper-1));
  box-shadow: var(--shadow-1);
  overflow: hidden;
  transition:
    translate var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out);
}

.canvas-card:hover {
  translate: 0 -0.35rem;
  border-color: var(--line-strong);
  box-shadow: var(--shadow-2);
}

.card-visual {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: color-mix(in oklab, var(--paper-0) 74%, var(--paper-1));
}

.cover {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4.15;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--paper-2);
}

.cover img,
.cover-empty {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.cover-empty {
  display: grid;
  place-items: center;
  background: var(--ink-0);
  color: var(--paper-0);
  font-family: var(--font-mono);
}

.id-stamp {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  padding: var(--space-0-5) var(--space-2);
  background: color-mix(in oklab, var(--ink-0) 78%, transparent);
  color: var(--paper-0);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  letter-spacing: 0.08em;
}

.reading-stamp {
  position: absolute;
  left: var(--space-2);
  bottom: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-0-5) var(--space-2);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  letter-spacing: 0.04em;
  font-weight: 500;
  z-index: 2;
  box-shadow: var(--shadow-1);
}

.reading-stamp.is-completed {
  background: color-mix(in oklab, var(--paper-0) 88%, var(--paper-1));
  color: var(--ink-1);
  border: 1px solid color-mix(in oklab, var(--line) 85%, transparent);
}

.reading-stamp.is-reading {
  background: color-mix(in oklab, var(--accent) 92%, black 8%);
  color: var(--paper-0);
  border: 1px solid color-mix(in oklab, var(--paper-0) 28%, transparent);
}

.card-visual[data-completed='true'] {
  opacity: 0.82;
  filter: grayscale(0.12);
}

.body {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: var(--space-4);
}

.title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 600;
  line-height: 1.25;
  min-height: 2.5em;
}

.meta {
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: auto;
  padding-top: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

@media (max-width: 220px) {
  .foot {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-1);
  }
}

.hitbox {
  display: block;
  width: 100%;
  height: 100%;
}

.hitbox:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}
</style>

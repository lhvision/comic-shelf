<script setup lang="ts">
import { computed } from 'vue'
import type { LibrarySummary } from '@/types'
import FavoriteButton from '@/components/FavoriteButton.vue'
import CacheProgress from '@/components/CacheProgress.vue'
const props = defineProps<{
  comic: LibrarySummary
  /** 实时缓存进度（后台任务运行时更新），优先于 comic.cached_pages */
  cache?: { running: boolean; cached: number; total: number }
}>()

const emit = defineEmits<{
  favoriteToggled: [source: string, sourceId: string, favorite: boolean]
}>()

const route = computed(() => `/comic/${props.comic.source}/${props.comic.source_id}`)

const deckCovers = computed(() => props.comic.cover_paths.slice(1, 4))
const primaryTags = computed(() => props.comic.tags.slice(0, 3))

const liveCached = computed(() => props.cache?.cached ?? props.comic.cached_pages)
const liveTotal = computed(() => props.cache?.total || props.comic.page_count)
const liveRunning = computed(() => Boolean(props.cache?.running))
</script>

<template>
  <article class="comic-card">
    <RouterLink :to="route" class="card-link">
      <div class="cover-deck">
        <FavoriteButton
          :source="comic.source"
          :source-id="comic.source_id"
          :favorite="comic.favorite"
          @toggled="(value) => emit('favoriteToggled', comic.source, comic.source_id, value)"
        />
        <div
          v-for="(cover, index) in deckCovers"
          :key="cover"
          class="deck-leaf"
          :style="{ '--deck-index': index, backgroundImage: `url(${cover})` }"
        />
        <div class="cover-front">
          <img
            v-if="comic.cover_paths[0]"
            class="cover-image"
            :src="comic.cover_paths[0]"
            :alt="`${comic.title} 封面`"
            loading="lazy"
            decoding="async"
          />
          <div v-else class="cover-placeholder">
            <span>{{ comic.display_id }}</span>
          </div>
          <span class="id-stamp">{{ comic.display_id }}</span>
        </div>
      </div>

      <div class="card-body">
        <h2 class="card-title line-clamp-2">{{ comic.title }}</h2>
        <p class="card-meta">{{ comic.authors.join(' / ') || '佚名' }} · {{ comic.page_count }}P</p>
        <div v-if="primaryTags.length" class="cluster card-tags">
          <span v-for="tag in primaryTags" :key="tag" class="chip">{{ tag }}</span>
        </div>
        <div class="card-foot">
          <span class="views">{{ comic.views }} 次观看</span>
          <CacheProgress :cached="liveCached" :total="liveTotal" :running="liveRunning" />
        </div>
      </div>
    </RouterLink>
  </article>
</template>

<style scoped>
.comic-card {
  container-type: inline-size;
}

.card-link {
  display: block;
  height: 100%;
  border-radius: var(--radius-3);
  background: color-mix(in oklab, var(--paper-0) 74%, var(--paper-1));
  border: 1px solid var(--line);
  box-shadow: var(--shadow-1);
  overflow: hidden;
  transition:
    translate var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out);
}

.card-link:hover {
  translate: 0 -0.35rem;
  border-color: var(--line-strong);
  box-shadow: var(--shadow-2);
}

.cover-deck {
  position: relative;
  aspect-ratio: 3 / 4.15;
  padding: 9% 10% 0;
  perspective: 60rem;
}

.deck-leaf {
  position: absolute;
  inset: 7% 16% 0;
  border-radius: var(--radius-2);
  background-color: var(--paper-2);
  background-size: cover;
  background-position: center top;
  border: 1px solid color-mix(in oklab, var(--ink-0) 12%, transparent);
  transform-origin: center bottom;
  transform: translateX(calc((var(--deck-index, 0) - 1) * 13%))
    rotate(calc((var(--deck-index, 0) - 1) * -5deg)) translateY(calc(var(--deck-index, 0) * 3%));
  opacity: 0.48;
  filter: saturate(0.6) brightness(0.92);
  transition: transform var(--duration-3) var(--ease-out);
}

.cover-front {
  position: relative;
  height: 100%;
  border-radius: var(--radius-2);
  overflow: hidden;
  border: 1px solid color-mix(in oklab, var(--ink-0) 14%, transparent);
  box-shadow: var(--shadow-2);
  transform-origin: center bottom;
  transition: transform var(--duration-3) var(--ease-out);
}

.card-link:hover .cover-front {
  transform: rotateX(-3deg) rotateY(4deg) translateY(-0.35rem);
}

.card-link:hover .deck-leaf {
  transform: translateX(calc((var(--deck-index, 0) - 1) * 16%))
    rotate(calc((var(--deck-index, 0) - 1) * -7deg)) translateY(calc(var(--deck-index, 0) * 4%));
  opacity: 0.7;
}

.cover-image,
.cover-placeholder {
  width: 100%;
  height: 100%;
}

.cover-image {
  object-fit: cover;
}

.cover-placeholder {
  display: grid;
  place-items: center;
  background:
    linear-gradient(135deg, var(--paper-1), var(--paper-2)),
    color-mix(in oklab, var(--paper-2) 70%, transparent);
  color: var(--ink-0);
  font-family: var(--font-mono);
  position: relative;
}

.cover-placeholder::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 3px;
  translate: -50% 0;
  background: color-mix(in oklab, var(--accent) 35%, transparent);
}

.id-stamp {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  padding: var(--space-0-5) var(--space-2);
  background: color-mix(in oklab, var(--ink-0) 82%, transparent);
  color: var(--paper-0);
  border: 1px solid color-mix(in oklab, var(--paper-0) 22%, transparent);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  letter-spacing: 0.08em;
  backdrop-filter: blur(4px);
}

.card-body {
  padding: var(--space-4);
}

.card-title {
  font-size: var(--text-md);
  min-height: 2.4em;
}

.card-meta {
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.card-tags {
  margin-top: var(--space-3);
}

.card-foot {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

@container (max-width: 380px) {
  .card-foot {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-1);
  }
}
</style>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LibrarySummary } from '@/types'
import FavoriteButton from '@/components/FavoriteButton.vue'
import CacheProgress from '@/components/CacheProgress.vue'
import AppTextClamp from '@/components/AppTextClamp.vue'
import AppChip from '@/components/AppChip.vue'
import { api, coverSrcset, pageFileUrl } from '@/api/client'
import { useCoverTransition } from '@/composables/useCoverTransition'
import { useAuth } from '@/composables/useAuth'
import { isCompletedComic, isInProgressComic } from '@/utils/is'

const props = defineProps<{
  comic: LibrarySummary
  /** 实时缓存进度（后台任务运行时更新），优先于 comic.cached_pages */
  cache?: { running: boolean; cached: number; total: number }
  /** 以图搜图匹配结果 */
  searchMatch?: { bestMatchPage: number; bestScore: number }
}>()

const emit = defineEmits<{
  favoriteToggled: [source: string, sourceId: string, favorite: boolean]
}>()

const { isCoverActive, setActiveCover } = useCoverTransition()
const { authenticated } = useAuth()

const isDeckActive = ref(false)
function loadDeck() {
  if (!isDeckActive.value) {
    isDeckActive.value = true
  }
}

/** 意图预热：在读者悬停或触碰卡片时预加载目标路由 chunk 与详情 API 数据 */
function prefetch() {
  loadDeck()
  void import('@/views/ComicDetailView.vue').catch(() => {})
  void api.detail(props.comic.source, props.comic.source_id).catch(() => {})
}

const route = computed(() => `/comic/${props.comic.source}/${props.comic.source_id}`)

const deckCovers = computed(() => props.comic.cover_paths.slice(1, 4))
const primaryTags = computed(() => props.comic.tags.slice(0, 3))

const liveCached = computed(() => props.cache?.cached ?? props.comic.cached_pages)
const liveTotal = computed(() => props.cache?.total || props.comic.page_count)
const liveRunning = computed(() => Boolean(props.cache?.running))
const isTargetCover = computed(() => isCoverActive(props.comic.source, props.comic.source_id))
const isCompleted = computed(() => isCompletedComic(props.comic))
const isInProgress = computed(() => isInProgressComic(props.comic))

const coverFailed = ref(false)
function onCoverError() {
  if (!coverFailed.value) {
    coverFailed.value = true
  }
}
const effectiveCover = computed(() => {
  if (coverFailed.value) {
    return pageFileUrl(props.comic.source, props.comic.source_id, 1)
  }
  return props.comic.cover_paths[0] || pageFileUrl(props.comic.source, props.comic.source_id, 1)
})
</script>

<template>
  <article
    class="comic-card"
    :data-completed="isCompleted"
    @pointerenter.once="prefetch"
    @focusin.once="prefetch"
    @touchstart.passive.once="prefetch"
  >
    <RouterLink
      :to="route"
      class="card-link"
      @click="setActiveCover(comic.source, comic.source_id)"
    >
      <div class="cover-deck">
        <FavoriteButton
          :source="comic.source"
          :source-id="comic.source_id"
          :favorite="comic.favorite"
          :interactive="authenticated"
          @toggled="(value) => emit('favoriteToggled', comic.source, comic.source_id, value)"
        />

        <div
          v-for="(cover, index) in deckCovers"
          :key="cover"
          class="deck-leaf"
          :data-deck-index="index"
        >
          <img
            v-if="isDeckActive"
            class="deck-leaf-img"
            :src="cover"
            :srcset="coverSrcset(cover)"
            sizes="(max-width: 680px) calc(50vw - 1.5rem), (max-width: 1200px) 25vw, 240px"
            alt=""
            loading="lazy"
            decoding="async"
            aria-hidden="true"
          />
        </div>
        <div
          class="cover-front"
          :style="isTargetCover ? { viewTransitionName: 'comic-cover-active' } : undefined"
        >
          <img
            v-if="effectiveCover"
            class="cover-image"
            :src="effectiveCover"
            :srcset="coverFailed ? undefined : coverSrcset(effectiveCover)"
            sizes="(max-width: 680px) calc(50vw - 1.5rem), (max-width: 1200px) 25vw, 240px"
            :alt="`${comic.title} 封面`"
            loading="lazy"
            decoding="async"
            @error="onCoverError"
          />
          <div v-else class="cover-placeholder">
            <span>{{ comic.display_id }}</span>
          </div>
          <span v-if="isCompleted" class="reading-stamp is-completed" title="全书已读完">
            已读完
          </span>
          <span
            v-else-if="isInProgress"
            class="reading-stamp is-reading"
            :title="`上次翻至第 ${comic.last_page} 页`"
          >
            {{ comic.last_page }}P / {{ comic.page_count }}P
          </span>
          <span class="id-stamp">{{ comic.display_id }}</span>
          <RouterLink
            v-if="searchMatch"
            :to="`/comic/${comic.source}/${comic.source_id}/read/${searchMatch.bestMatchPage}`"
            class="match-stamp"
            @click.stop
            :title="`第 ${searchMatch.bestMatchPage} 页匹配度 ${Math.round(searchMatch.bestScore * 100)}%，点击直接阅读`"
          >
            P.{{ searchMatch.bestMatchPage }} · {{ Math.round(searchMatch.bestScore * 100) }}%
          </RouterLink>
        </div>
      </div>

      <div class="card-body">
        <AppTextClamp
          as="h2"
          class="card-title"
          :lines="2"
          :text="comic.title"
          :delay="350"
          tooltip-align="end"
          tooltip-side="top"
          tooltip-width="22rem"
        />
        <AppTextClamp
          as="p"
          class="card-meta"
          :lines="1"
          :text="`${comic.authors.join(' / ') || '佚名'} · ${comic.page_count}P`"
          :delay="350"
          tooltip-align="end"
          tooltip-side="bottom"
          tooltip-width="24rem"
        />
        <div v-if="primaryTags.length" class="cluster card-tags">
          <AppChip v-for="tag in primaryTags" :key="tag">{{ tag }}</AppChip>
        </div>
        <div class="card-foot">
          <span v-if="comic.views" class="views">{{ comic.views }} 次观看</span>
          <CacheProgress :cached="liveCached" :total="liveTotal" :running="liveRunning" />
        </div>
      </div>
    </RouterLink>
  </article>
</template>

<style scoped>
.comic-card {
  container-type: inline-size;
  contain: layout style;
  height: 100%;
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-spring);
}

@starting-style {
  .comic-card {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
}

.card-link {
  display: flex;
  flex-direction: column;
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

/* Hover Hysteresis Guard: 锚定至静止宿主容器 .comic-card，杜绝位移导致光标反复脱靶的高频抖动 */
.comic-card:hover .card-link,
.comic-card:focus-within .card-link,
.card-link:focus-visible {
  translate: 0 -0.35rem;
  border-color: var(--line-strong);
  box-shadow: var(--shadow-2);
}

.cover-deck {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4.15;
  flex-shrink: 0;
}

.comic-card:hover .cover-deck,
.comic-card:focus-within .cover-deck,
.card-link:focus-visible .cover-deck {
  perspective: 60rem;
}

.deck-leaf {
  position: absolute;
  inset: 7% 16% 0;
  border-radius: var(--radius-2);
  background-color: color-mix(in oklab, var(--paper-2) 88%, var(--ink-2) 12%);
  overflow: hidden;
  border: 1px solid color-mix(in oklab, var(--ink-0) 12%, transparent);
  transform-origin: center bottom;
  opacity: 0.48;
  transition: transform var(--duration-3) var(--ease-out);
}

.deck-leaf-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center top;
  display: block;
}

.deck-leaf[data-deck-index='0'] {
  transform: translateX(-13%) rotate(5deg);
}

.deck-leaf[data-deck-index='1'] {
  transform: translateX(0) rotate(0deg) translateY(3%);
}

.deck-leaf[data-deck-index='2'] {
  transform: translateX(13%) rotate(-5deg) translateY(6%);
}

.comic-card:hover .deck-leaf[data-deck-index='0'],
.comic-card:focus-within .deck-leaf[data-deck-index='0'],
.card-link:focus-visible .deck-leaf[data-deck-index='0'] {
  transform: translateX(-16%) rotate(7deg);
}

.comic-card:hover .deck-leaf[data-deck-index='1'],
.comic-card:focus-within .deck-leaf[data-deck-index='1'],
.card-link:focus-visible .deck-leaf[data-deck-index='1'] {
  transform: translateX(0) rotate(0deg) translateY(4%);
}

.comic-card:hover .deck-leaf[data-deck-index='2'],
.comic-card:focus-within .deck-leaf[data-deck-index='2'],
.card-link:focus-visible .deck-leaf[data-deck-index='2'] {
  transform: translateX(16%) rotate(-7deg) translateY(8%);
}

.cover-front {
  position: absolute;
  inset: 9% 10% 0;
  border-radius: var(--radius-2);
  overflow: hidden;
  border: 1px solid color-mix(in oklab, var(--ink-0) 14%, transparent);
  box-shadow: var(--shadow-2);
  transform-origin: center bottom;
  transition: transform var(--duration-3) var(--ease-out);
}

.comic-card:hover .cover-front,
.comic-card:focus-within .cover-front,
.card-link:focus-visible .cover-front {
  transform: rotateX(-3deg) rotateY(4deg) translateY(-0.35rem);
}

.cover-image,
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: block;
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
  background: color-mix(in oklab, var(--ink-0) 88%, transparent);
  color: var(--paper-0);
  border: 1px solid color-mix(in oklab, var(--paper-0) 24%, transparent);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  letter-spacing: 0.08em;
  box-shadow: 0 1px 3px rgb(0 0 0 / 28%);
}

.match-stamp {
  position: absolute;
  left: var(--space-2);
  top: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-0-5) var(--space-2);
  background: color-mix(in oklab, var(--accent) 92%, black 8%);
  color: var(--paper-0);
  border: 1px solid color-mix(in oklab, var(--paper-0) 30%, transparent);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  letter-spacing: 0.04em;
  font-weight: 600;
  text-decoration: none;
  box-shadow: var(--shadow-1);
  z-index: 2;
  transition: opacity var(--duration-1) var(--ease-out);
}

.match-stamp:hover {
  opacity: 0.88;
}

.card-body {
  display: flex;
  flex-direction: column;
  flex: 1;
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
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: auto;
  padding-top: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

@container (max-width: 220px) {
  .card-foot {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-1);
  }
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

.comic-card[data-completed='true'] .card-link {
  opacity: 0.82;
  filter: grayscale(0.12);
}

.comic-card[data-completed='true']:hover .card-link,
.comic-card[data-completed='true']:focus-within .card-link,
.comic-card[data-completed='true'] .card-link:focus-visible {
  opacity: 1;
  filter: none;
}
</style>

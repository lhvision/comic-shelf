<script setup lang="ts">
/**
 * 阅读器结尾卡 —— "本子翻完了" 与 "接卷推荐"。
 * 1. 呈现实体书卷末印章与完成提示；
 * 2. 推荐至多 3 本未读/在读精选藏书，支持点击直接开读与查看详情；
 * 3. 底部提供“回到详情”与“返回书架”导航入口。
 */
import { ref } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import type { LibrarySummary } from '@/types'
import AppTextClamp from '@/components/AppTextClamp.vue'
import AppIcon from '@/components/AppIcon.vue'
import { coverSrcset } from '@/api/client'

withDefaults(
  defineProps<{
    /** 横向模式下列为可吸附的整屏卡片 */
    snap?: boolean
    /** 接卷推荐藏书列表（至多 3 本） */
    recommendations?: LibrarySummary[]
  }>(),
  {
    snap: false,
    recommendations: () => [],
  },
)

const emit = defineEmits<{
  back: []
  home: []
  select: [source: string, sourceId: string]
  detail: [source: string, sourceId: string]
  completed: []
}>()

const cardEl = ref<HTMLElement | null>(null)
let hasTriggeredCompleted = false

// 真实视口感知：仅当读者真正滑阅至末页卡片且在视口呈现时，才判定为全卷读完
useIntersectionObserver(
  cardEl,
  (entries) => {
    const entry = entries[0]
    if (entry?.isIntersecting && !hasTriggeredCompleted) {
      hasTriggeredCompleted = true
      emit('completed')
    }
  },
  { threshold: 0.15 },
)
</script>

<template>
  <div ref="cardEl" class="reader-end" :data-snap="snap">
    <div class="reader-end-container">
      <header class="reader-end-header">
        <span class="end-seal">〔 全卷完 · 归阁 〕</span>
        <h2 class="end-title">本子翻完了</h2>
        <p class="end-sub">
          {{
            recommendations && recommendations.length > 0
              ? '合上书卷，墨香犹在。接下来想读哪一部？'
              : '合上书卷，墨香犹在。当前藏书均已翻阅完毕。'
          }}
        </p>
      </header>

      <section
        v-if="recommendations && recommendations.length > 0"
        class="recommend-section"
        aria-label="接卷阅览推荐"
      >
        <div class="recommend-header">
          <AppIcon name="book-open" size="sm" class="rec-icon" />
          <span class="recommend-eyebrow">接卷阅览 · 接着翻翻</span>
        </div>

        <div class="recommend-grid">
          <article
            v-for="item in recommendations"
            :key="`${item.source}/${item.source_id}`"
            class="rec-card"
          >
            <div
              class="rec-card-main"
              role="button"
              tabindex="0"
              :aria-label="`直接阅读 ${item.title}`"
              @click="$emit('select', item.source, item.source_id)"
              @keydown.enter="$emit('select', item.source, item.source_id)"
              @keydown.space.prevent="$emit('select', item.source, item.source_id)"
            >
              <div class="rec-cover-wrap">
                <img
                  v-if="item.cover_paths && item.cover_paths[0]"
                  class="rec-cover-img"
                  :src="item.cover_paths[0]"
                  :srcset="coverSrcset(item.cover_paths[0])"
                  sizes="(max-width: 680px) 180px, 220px"
                  :alt="item.title"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="rec-cover-placeholder">
                  <span>{{ item.display_id }}</span>
                </div>

                <span v-if="(item.last_page ?? 0) > 0" class="rec-status-badge is-reading">
                  在读 {{ item.last_page }}P
                </span>
                <span v-else class="rec-status-badge is-unread"> 未读 </span>
              </div>

              <div class="rec-info">
                <AppTextClamp as="h3" class="rec-title" :lines="1" :text="item.title" />
                <AppTextClamp
                  as="p"
                  class="rec-author"
                  :lines="1"
                  :text="item.authors.join(' / ') || '佚名'"
                />
              </div>
            </div>

            <button
              class="rec-detail-btn icon-btn"
              type="button"
              title="查看作品详情"
              aria-label="查看作品详情"
              @click.stop="$emit('detail', item.source, item.source_id)"
            >
              <AppIcon name="info" size="sm" />
            </button>
          </article>
        </div>
      </section>

      <footer class="reader-end-actions">
        <button class="btn btn-primary end-btn" type="button" @click="$emit('back')">
          <AppIcon name="arrow-left" size="sm" />
          <span>回到详情</span>
        </button>
        <button class="btn btn-ghost end-btn" type="button" @click="$emit('home')">
          <AppIcon name="archive" size="sm" />
          <span>返回书架</span>
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.reader-end {
  flex: 0 0 100%;
  min-width: 100%;
  min-height: 100dvh;
  display: grid;
  place-content: center;
  justify-items: center;
  text-align: center;
  padding: calc(var(--reader-chrome-h) + var(--space-4)) var(--space-4);
  color: var(--reader-text);
  box-sizing: border-box;
}

.reader-end[data-snap='true'] {
  scroll-snap-align: start;
}

.reader-end-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  max-width: 48rem;
  margin: 0 auto;
}

.reader-end-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.end-seal {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  letter-spacing: 0.12em;
  color: var(--accent);
  padding: var(--space-0-5) var(--space-2);
  border: 1px solid color-mix(in oklab, var(--accent) 45%, transparent);
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--accent) 10%, transparent);
}

.end-title {
  font-family: var(--font-serif);
  font-size: var(--text-2xl);
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--reader-text);
  margin: 0;
}

.end-sub {
  font-size: var(--text-sm);
  color: color-mix(in oklab, var(--reader-text) 62%, transparent);
  margin: 0;
}

.recommend-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
}

.recommend-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: color-mix(in oklab, var(--reader-text) 75%, transparent);
}

.rec-icon {
  color: var(--accent);
}

.recommend-eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
}

.recommend-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
  width: 100%;
}

.rec-card {
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0) 6%, var(--reader-bg));
  border: 1px solid color-mix(in oklab, var(--paper-0) 12%, transparent);
  box-shadow: var(--shadow-2);
  overflow: hidden;
  transition:
    transform var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out);
}

.rec-card:hover {
  transform: translateY(-3px);
  border-color: color-mix(in oklab, var(--accent) 65%, transparent);
  box-shadow: var(--shadow-3);
}

.rec-card-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  text-align: left;
  cursor: pointer;
  outline: none;
}

.rec-card-main:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.rec-cover-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4.2;
  overflow: hidden;
  background: var(--reader-bg);
}

.rec-cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.rec-cover-placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.rec-status-badge {
  position: absolute;
  left: var(--space-2);
  bottom: var(--space-2);
  padding: var(--space-0-5) var(--space-1-5);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  letter-spacing: 0.04em;
  font-weight: 500;
}

.rec-status-badge.is-reading {
  background: color-mix(in oklab, var(--accent) 90%, black 10%);
  color: var(--paper-0);
  border: 1px solid color-mix(in oklab, var(--paper-0) 25%, transparent);
}

.rec-status-badge.is-unread {
  background: color-mix(in oklab, var(--paper-0) 10%, var(--reader-bg));
  color: color-mix(in oklab, var(--reader-text) 85%, transparent);
  border: 1px solid color-mix(in oklab, var(--paper-0) 18%, transparent);
}

.rec-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  background: color-mix(in oklab, var(--paper-0) 4%, var(--reader-bg));
}

.rec-title {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--reader-text);
  margin: 0;
}

.rec-author {
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  color: color-mix(in oklab, var(--reader-text) 55%, transparent);
  margin: 0;
}

.rec-detail-btn {
  position: absolute;
  right: var(--space-2);
  top: var(--space-2);
  width: 2rem;
  height: 2rem;
  min-width: 2rem;
  min-height: 2rem;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--paper-0) 8%, var(--reader-bg));
  color: color-mix(in oklab, var(--reader-text) 85%, transparent);
  border: 1px solid color-mix(in oklab, var(--paper-0) 18%, transparent);
  cursor: pointer;
  z-index: 2;
  transition:
    color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

/* 扩展触控热区至 ≥ 44×44px，满足移动端无障碍底线 */
.rec-detail-btn::before {
  content: '';
  position: absolute;
  inset: -6px;
}

.rec-detail-btn:hover {
  color: var(--paper-0);
  background: color-mix(in oklab, var(--accent) 85%, black 15%);
  border-color: color-mix(in oklab, var(--paper-0) 30%, transparent);
}

.reader-end-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.end-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2.75rem;
  padding: 0 var(--space-5);
  font-size: var(--text-sm);
}

@media (max-width: 680px) {
  .recommend-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .rec-card-main {
    flex-direction: row;
    align-items: center;
  }

  .rec-cover-wrap {
    width: 3.5rem;
    flex-shrink: 0;
  }

  .rec-status-badge {
    font-size: 0.625rem;
    padding: 1px var(--space-1);
    left: var(--space-1);
    bottom: var(--space-1);
  }

  .rec-info {
    flex: 1;
    min-width: 0;
    padding-right: var(--space-8);
  }

  .reader-end-actions {
    flex-direction: column;
    width: 100%;
  }

  .end-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>

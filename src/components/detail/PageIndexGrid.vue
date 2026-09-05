<script setup lang="ts">
import { nextTick, ref } from 'vue'
import PageTile from '@/components/detail/PageTile.vue'
import AppIcon from '@/components/AppIcon.vue'
import type { PageRecord } from '@/types'

/**
 * 详情页「页面索引」整段 —— 标题 + 缩略图网格 + 尾格余量徽印 + 步进/全量折叠架。
 *
 * 彻底废除基于长距离 useIntersectionObserver 的贪婪无限滚动（根治长滚动条失控痛点）。
 * 结合 XboxYan 尾格印章哲学，当存在未展开画页时：
 * 1. 列表末尾独立追加「余页收纳」折叠卡（.page-tile-overflow），杜绝遮罩覆盖导致的幽灵焦点，点击就地展开下一批；
 * 2. 底部控制槽位提供「展开全部」与「收起画卷」，主动掌控权交还读者。
 */
const props = withDefaults(
  defineProps<{
    source: string
    sourceId: string
    /** 当前已渲染的页面（前面若干页） */
    pages: PageRecord[]
    /** 还剩多少页没有展开 */
    remainingPages: number
    /** 每次增量加载的步长 */
    pageStep: number
    /** 计数文案，如「已显示 24 / 120 页」 */
    showingRange: string
    /** 当前章节文案（如「第 2 話 · 标题」）；单章节作品为空字符串。 */
    chapterLabel?: string
    /** 章节起始全局页码（1-based）：传了则 tile 显示本章本地页码 */
    chapterStart?: number
    /** 来源章节 id：阅读器返回时回到该章节子路由 */
    chapterId?: string
    /** 是否处于已展开状态（支持收起） */
    canCollapse?: boolean
  }>(),
  {
    chapterLabel: '',
    chapterStart: undefined,
    chapterId: '',
    canCollapse: false,
  },
)

const emit = defineEmits<{
  loadMore: []
  loadAll: []
  collapse: []
}>()

const sectionEl = ref<HTMLElement | null>(null)

function localLabel(page: PageRecord) {
  return props.chapterStart ? page.index - props.chapterStart + 1 : page.index
}

function handleCollapse() {
  emit('collapse')
  void nextTick(() => {
    if (sectionEl.value && typeof sectionEl.value.scrollIntoView === 'function') {
      sectionEl.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}
</script>

<template>
  <section ref="sectionEl" class="page-section" aria-labelledby="pages-title">
    <div class="page-section-head">
      <div>
        <p class="eyebrow">All pages</p>
        <h2 id="pages-title">页面索引</h2>
      </div>
      <p>点击任意页面直接进入阅读</p>
    </div>

    <div class="page-meta-row">
      <span class="page-count-note">
        {{ chapterLabel ? `${chapterLabel} · ` : '' }}{{ showingRange }}
      </span>
      <span v-if="remainingPages > 0" class="page-remaining-chip">
        余 {{ remainingPages }} 页已收纳
      </span>
    </div>

    <TransitionGroup tag="div" name="folio-card" class="page-grid">
      <PageTile
        v-for="page in pages"
        :key="page.index"
        :source="source"
        :source-id="sourceId"
        :index="page.index"
        :cached="page.cached"
        :label="localLabel(page)"
        :chapter-id="chapterId"
      />

      <!-- 画卷余页尾格折叠卡：独立排布在网格最后，结构与首页书架保持高度一致 -->
      <div
        v-if="remainingPages > 0"
        key="page-fold-card"
        class="page-fold-card page-tile-overflow surface"
        role="region"
        aria-label="画卷余页折叠收纳卡"
      >
        <div class="fold-card-body">
          <div class="fold-badge-wrap">
            <AppIcon name="book-open" size="xs" class="fold-badge-icon" />
            <span class="fold-badge-stamp">+{{ remainingPages }} 页已收纳</span>
          </div>
          <h4 class="fold-card-title">画卷余页已收纳</h4>
          <p class="fold-card-hint">
            案头展示前 {{ pages.length }} 页，还有 {{ remainingPages }} 页画卷已折叠。
          </p>
          <div class="fold-card-actions">
            <button
              class="btn btn-primary btn-small"
              type="button"
              @click.prevent="emit('loadMore')"
            >
              <AppIcon name="chevron-down" size="xs" />
              再展开 {{ Math.min(pageStep, remainingPages) }} 页
            </button>
            <button class="btn btn-ghost btn-small" type="button" @click.prevent="emit('loadAll')">
              <AppIcon name="book-open" size="xs" />
              展开全部
            </button>
            <button
              v-if="canCollapse"
              class="btn btn-ghost btn-small"
              type="button"
              @click.prevent="handleCollapse"
            >
              <AppIcon name="chevron-up" size="xs" />
              收起画卷
            </button>
          </div>
        </div>
      </div>
    </TransitionGroup>

    <!-- 全卷画页全量展开后的收整条：折叠态收敛至网格卡片内部，全部展开后呈现底部收起条 -->
    <div v-if="canCollapse && remainingPages === 0" class="page-sentinel page-fold-bar surface">
      <div class="sentinel-info">
        <AppIcon name="book-open" size="sm" class="sentinel-icon" />
        <span class="sentinel-note">
          已呈现 {{ pages.length }} / {{ pages.length }} 页画卷（全卷画页已展开）
        </span>
      </div>

      <div class="sentinel-actions">
        <button class="btn btn-ghost btn-small" type="button" @click.prevent="handleCollapse">
          <AppIcon name="chevron-up" size="xs" />
          收起画卷
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.page-section {
  margin-top: var(--space-8);
}

.page-section-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--line);
}

.page-section-head h2 {
  font-size: var(--text-2xl);
}

.page-section-head p {
  color: var(--ink-2);
  font-size: var(--text-sm);
}

.page-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-3);
}

.page-count-note {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.page-remaining-chip {
  display: inline-flex;
  align-items: center;
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--accent);
  background: color-mix(in oklab, var(--accent) 10%, transparent);
  border: 1px solid color-mix(in oklab, var(--accent) 22%, transparent);
  padding: 0.1rem var(--space-2);
  border-radius: var(--radius-pill);
}

.page-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(7.5rem, 30vw), 1fr));
  gap: var(--space-4);
  margin-top: var(--space-5);
}

.page-fold-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: var(--space-3) var(--space-2);
  border-radius: var(--radius-3);
  border: 1px dashed color-mix(in oklab, var(--accent) 35%, var(--line-strong));
  background: color-mix(in oklab, var(--paper-1) 80%, transparent);
  text-align: center;
  height: 100%;
  min-height: 100%;
  aspect-ratio: 3 / 4.15;
  box-shadow: var(--shadow-1);
  transition:
    border-color var(--duration-2) var(--ease-out),
    background-color var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out);
}

.page-fold-card:hover {
  border-color: var(--accent);
  background: var(--paper-1);
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
}

.fold-card-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1-5);
  width: 100%;
  max-width: 10rem;
}

.fold-badge-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: color-mix(in oklab, var(--accent) 12%, transparent);
  padding: var(--space-0-5) var(--space-2);
  border-radius: var(--radius-pill);
  border: 1px solid color-mix(in oklab, var(--accent) 25%, transparent);
}

.fold-badge-icon {
  color: var(--accent);
}

.fold-badge-stamp {
  font-family: var(--font-display);
  font-size: var(--text-caption);
  font-weight: 700;
  color: var(--accent);
}

.fold-card-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-0);
  margin: 0;
  line-height: var(--leading-tight);
}

.fold-card-hint {
  font-size: var(--text-caption);
  color: var(--ink-2);
  margin: 0;
  line-height: var(--leading-snug);
}

.fold-card-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  width: 100%;
  margin-top: var(--space-1);
}

.fold-card-actions .btn {
  width: 100%;
  min-height: 1.85rem;
  padding: 0.2rem var(--space-1);
  font-size: var(--text-caption);
  gap: var(--space-1);
  justify-content: center;
  border-radius: var(--radius-1);
  white-space: nowrap;
}

.page-sentinel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
}

.sentinel-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sentinel-icon {
  color: var(--accent);
}

.sentinel-note {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
}

.sentinel-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

@media (max-width: 640px) {
  .page-fold-card {
    aspect-ratio: auto;
    min-height: 100%;
  }

  .page-sentinel {
    flex-direction: column;
    align-items: stretch;
  }

  .sentinel-actions {
    justify-content: flex-end;
  }

  .fold-card-actions .btn,
  .sentinel-actions .btn {
    min-height: 44px;
  }
}

/* 画页微动与进场动画 */
.folio-card-enter-active {
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-spring);
}

.folio-card-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}

.folio-card-move {
  transition: transform var(--duration-2) var(--ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .folio-card-enter-active,
  .folio-card-move {
    transition: none !important;
  }
}
</style>

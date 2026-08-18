<script setup lang="ts">
import { ref } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import PageTile from '@/components/detail/PageTile.vue'
import type { PageRecord } from '@/types'

/**
 * 详情页「页面索引」整段 —— 标题 + 已显示计数 + 缩略图网格 + 增量加载。
 *
 * 加载更多用 `useIntersectionObserver` 监听底部哨兵：
 * - 哨兵只在还有剩余页数时渲染（v-if），target 为空时观察自动停止；
 * - 滚动进入 700px rootMargin 视线即触发 `loadMore`。
 * 这替代了手写 IntersectionObserver + onBeforeUnmount disconnect 的样板。
 */
const props = defineProps<{
  source: string
  sourceId: string
  /** 当前已渲染的页面（前面若干页） */
  pages: PageRecord[]
  /** 还剩多少页没有展开 */
  remainingPages: number
  /** 每次增量加载的步长 */
  pageStep: number
  /** 计数文案，如「已显示 48 / 120 页」 */
  showingRange: string
}>()

const emit = defineEmits<{ loadMore: [] }>()

const loadMoreTrigger = ref<HTMLElement | null>(null)

useIntersectionObserver(
  loadMoreTrigger,
  (entries) => {
    if (entries[0]?.isIntersecting) emit('loadMore')
  },
  { rootMargin: '700px 0px' },
)
</script>

<template>
  <section class="page-section" aria-labelledby="pages-title">
    <div class="page-section-head">
      <div>
        <p class="eyebrow">All pages</p>
        <h2 id="pages-title">页面索引</h2>
      </div>
      <p>点击任意页面直接进入阅读</p>
    </div>

    <p class="page-count-note">{{ showingRange }}</p>

    <div class="page-grid">
      <PageTile
        v-for="page in pages"
        :key="page.index"
        :source="source"
        :source-id="sourceId"
        :index="page.index"
        :cached="page.cached"
      />
    </div>

    <div v-if="remainingPages > 0" ref="loadMoreTrigger" class="load-more">
      <p>后面还有 {{ remainingPages }} 页没有展开，避免一次性渲染卡顿。</p>
      <button class="btn btn-ghost btn-small" type="button" @click.prevent="emit('loadMore')">
        再显示 {{ Math.min(pageStep, remainingPages) }} 页
      </button>
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

.page-count-note {
  margin-top: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  text-align: right;
}

.page-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(7.5rem, 30vw), 1fr));
  gap: var(--space-4);
  margin-top: var(--space-5);
}

.load-more {
  display: grid;
  justify-items: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
  padding: var(--space-5);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius-2);
  color: var(--ink-2);
  font-size: var(--text-sm);
  text-align: center;
}
</style>

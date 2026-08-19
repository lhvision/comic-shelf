<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useLastRead } from '@/composables/useLastRead'
import { useChapterNavigation } from '@/composables/useChapterNavigation'
import { useToast } from '@/composables/useToast'
import ChapterSwitcher from '@/components/detail/ChapterSwitcher.vue'
import PageIndexGrid from '@/components/detail/PageIndexGrid.vue'
import type { ComicDetail } from '@/types'

/**
 * 章节子路由详情 —— 一本多话作品的「单个话」页面索引。
 *
 * 设计（对应 docs/agents/ui.md + Impeccable 234 步）：
 * 多章节作品在详情页只摆「章节目录」（ChapterIndex），不铺开几千页；
 * 点某话进入本子路由，只渲染这一话的页面索引 + 章节头（标题/页数/上一话/下一话）。
 * 阅读器沿用全局页码，因此本页 PageTile 仍链接全局页号。
 */
const route = useRoute()
const router = useRouter()
const { toast } = useToast()

const source = computed(() => String(route.params.source))
const sourceId = computed(() => String(route.params.sourceId))
const chapterId = computed(() => String(route.params.chapterId))

const detail = ref<ComicDetail | null>(null)
const loading = ref(true)

const lastRead = useLastRead(source, sourceId)
const nav = useChapterNavigation(detail, lastRead)

const activeChapter = computed(
  () => nav.chapters.value.find((c) => c.id === chapterId.value) ?? null,
)
const activeIndex = computed(() => nav.chapters.value.findIndex((c) => c.id === chapterId.value))
const prevChapter = computed(() => nav.chapters.value[activeIndex.value - 1] ?? null)
const nextChapter = computed(() => nav.chapters.value[activeIndex.value + 1] ?? null)

const chapterRange = computed(() => {
  const c = activeChapter.value
  if (!c) return ''
  const end = c.start + c.page_count - 1
  return `第 ${c.start}–${end} 全局页`
})

watch(
  chapterId,
  () => {
    nav.setChapterById(chapterId.value)
  },
  { immediate: true },
)

onMounted(load)

async function load() {
  loading.value = true
  try {
    detail.value = await api.detail(source.value, sourceId.value)
    nav.setChapterById(chapterId.value)
    // 单章节或无此章节时回落详情页
    if (!activeChapter.value) {
      router.replace(`/comic/${source.value}/${sourceId.value}`)
      return
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
    router.replace(`/comic/${source.value}/${sourceId.value}`)
  } finally {
    loading.value = false
  }
}

function goToAlbum() {
  router.push(`/comic/${source.value}/${sourceId.value}`)
}

function goToChapter(id: string) {
  router.push(`/comic/${source.value}/${sourceId.value}/chapter/${id}`)
}

function goPrev() {
  if (prevChapter.value) goToChapter(prevChapter.value.id)
}

function goNext() {
  if (nextChapter.value) goToChapter(nextChapter.value.id)
}
</script>

<template>
  <div class="chapter-view container">
    <div v-if="loading" class="chapter-loading">
      <div class="skeleton chapter-head-skeleton" />
      <div class="skeleton chapter-grid-skeleton" />
    </div>

    <template v-else-if="detail && activeChapter">
      <section class="chapter-head surface">
        <button
          class="chapter-back icon-btn"
          type="button"
          aria-label="返回本子详情"
          @click="goToAlbum"
        >
          <span aria-hidden="true">←</span>
        </button>

        <div class="chapter-head-main">
          <p class="eyebrow">第 {{ activeChapter.index }} 話</p>
          <h1>{{ activeChapter.title || `第 ${activeChapter.index} 話` }}</h1>
          <p class="chapter-head-meta">
            {{ activeChapter.page_count }} 页 · {{ chapterRange }} · 本子「{{ detail.meta.title }}」
          </p>
        </div>

        <div class="chapter-pager">
          <button class="btn btn-ghost" type="button" :disabled="!prevChapter" @click="goPrev">
            ← 上一话
          </button>
          <button class="btn btn-ghost" type="button" :disabled="!nextChapter" @click="goNext">
            下一话 →
          </button>
        </div>
      </section>

      <ChapterSwitcher
        :chapters="nav.chapters"
        :active-id="activeChapter.id"
        @change="goToChapter"
      />

      <PageIndexGrid
        :source="source"
        :source-id="sourceId"
        :chapter-label="nav.activeChapterLabel"
        :pages="nav.visiblePages"
        :remaining-pages="nav.remainingPages"
        :page-step="nav.pageStep"
        :showing-range="nav.showingRange"
        @load-more="nav.loadMore"
      />
    </template>
  </div>
</template>

<style scoped>
.chapter-view {
  padding-block: var(--space-6) var(--space-10);
}

.chapter-loading {
  display: grid;
  gap: var(--space-5);
}

.chapter-head-skeleton {
  height: 12rem;
}

.chapter-grid-skeleton {
  height: 30rem;
}

.chapter-head {
  position: relative;
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6) var(--space-6) var(--space-6);
}

.chapter-back {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  z-index: 2;
}

.chapter-head-main {
  padding-top: var(--space-4);
}

.chapter-head-main h1 {
  margin-top: var(--space-2);
  font-family: var(--font-display);
  font-size: var(--text-xl);
  line-height: var(--leading-tight);
}

.chapter-head-meta {
  margin-top: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.chapter-pager {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  border-top: 1px solid var(--line);
  padding-top: var(--space-4);
}

@media (max-width: 640px) {
  .chapter-head {
    padding-inline: var(--space-4);
  }

  .chapter-pager .btn {
    flex: 1 1 8rem;
  }
}
</style>

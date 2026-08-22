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
 *
 * ⚠️ 必须把 composable 的 Ref 解构到 setup 顶层再喂给模板/子组件（普通对象属性
 * `nav.xxx` 不会自动 unwrap，会导致 `props.chapters.findIndex is not a function`、图片不显示）。
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
const {
  chapters,
  activeChapterLabel,
  visiblePages,
  remainingPages,
  showingRange,
  pageStep,
  loadMore,
  setChapterById,
} = useChapterNavigation(detail, lastRead)

const activeChapter = computed(() => chapters.value.find((c) => c.id === chapterId.value) ?? null)
const activeIndex = computed(() => chapters.value.findIndex((c) => c.id === chapterId.value))
const prevChapter = computed(() => chapters.value[activeIndex.value - 1] ?? null)
const nextChapter = computed(() => chapters.value[activeIndex.value + 1] ?? null)

const chapterRange = computed(() => {
  const c = activeChapter.value
  if (!c) return ''
  const end = c.start + c.page_count - 1
  return `第 ${c.start}–${end} 全局页`
})

watch(
  chapterId,
  () => {
    setChapterById(chapterId.value)
  },
  { immediate: true },
)

onMounted(load)

async function load() {
  loading.value = true
  try {
    detail.value = await api.detail(source.value, sourceId.value)
    setChapterById(chapterId.value)
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
        <div class="chapter-head-top">
          <button
            class="chapter-back icon-btn"
            type="button"
            aria-label="返回本子详情"
            @click="goToAlbum"
          >
            <span aria-hidden="true">←</span>
          </button>
          <p class="eyebrow">第 {{ activeChapter.index }} 話</p>
        </div>

        <h1>{{ activeChapter.title || `第 ${activeChapter.index} 話` }}</h1>
        <p class="chapter-head-meta">
          {{ activeChapter.index }} / {{ chapters.length }} 话 · {{ activeChapter.page_count }} 页 ·
          {{ chapterRange }} · 本子「{{ detail.meta.title }}」
        </p>

        <div class="chapter-pager">
          <button class="btn btn-ghost" type="button" :disabled="!prevChapter" @click="goPrev">
            ← 上一话
          </button>

          <ChapterSwitcher
            class="pager-tabs"
            :chapters="chapters"
            :active-id="activeChapter.id"
            in-pager
            @change="goToChapter"
          />

          <button class="btn btn-ghost" type="button" :disabled="!nextChapter" @click="goNext">
            下一话 →
          </button>
        </div>
      </section>

      <PageIndexGrid
        :source="source"
        :source-id="sourceId"
        :chapter-label="activeChapterLabel"
        :chapter-start="activeChapter.start"
        :chapter-id="activeChapter.id"
        :pages="visiblePages"
        :remaining-pages="remainingPages"
        :page-step="pageStep"
        :showing-range="showingRange"
        @load-more="loadMore"
      />
    </template>
  </div>
</template>

<style scoped>
.chapter-view {
  position: relative;
  isolation: isolate;
  overflow-x: clip;
  padding-block: var(--space-6) var(--space-10);
}

.chapter-head,
.chapter-loading,
:deep(.page-index-grid) {
  position: relative;
  z-index: 1;
}

.chapter-loading {
  display: grid;
  gap: var(--space-5);
}

.chapter-head-skeleton {
  height: 11rem;
}

.chapter-grid-skeleton {
  height: 30rem;
}

.chapter-head {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
}

.chapter-head-top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chapter-head h1 {
  margin-top: var(--space-1);
  font-family: var(--font-display);
  font-size: var(--text-xl);
  line-height: var(--leading-tight);
}

.chapter-head-meta {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.chapter-pager {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  border-top: 1px solid var(--line);
  margin-top: var(--space-2);
  padding-top: var(--space-3);
  min-width: 0;
}

.pager-tabs {
  display: flex;
}

@media (max-width: 720px) {
  .chapter-pager {
    flex-wrap: wrap;
  }

  .chapter-pager > .btn {
    flex: 1 1 6rem;
  }

  .pager-tabs {
    flex: 1 1 100%;
    order: 3;
  }
}
</style>

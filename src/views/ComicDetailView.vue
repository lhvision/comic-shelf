<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useIntervalFn } from '@vueuse/core'
import { api, pageFileUrl } from '@/api/client'
import { useLastRead } from '@/composables/useLastRead'
import { useChapterNavigation } from '@/composables/useChapterNavigation'
import { useIdlePrefetch } from '@/composables/useIdlePrefetch'
import { useLibraryStore, createPlaceholderDetail } from '@/stores/library'
import { useToast } from '@/composables/useToast'
import { useCoverTransition } from '@/composables/useCoverTransition'
import { useAuth } from '@/composables/useAuth'
import CoverCarousel from '@/components/CoverCarousel.vue'
import AppIcon from '@/components/AppIcon.vue'

import DetailActionBar from '@/components/detail/DetailActionBar.vue'
import ChapterIndex from '@/components/detail/ChapterIndex.vue'
import MetadataPanel from '@/components/MetadataPanel.vue'
import PageIndexGrid from '@/components/detail/PageIndexGrid.vue'
import EditMetadataModal from '@/components/detail/EditMetadataModal.vue'
import AppendPagesModal from '@/components/detail/AppendPagesModal.vue'
import ReplacePagesModal from '@/components/detail/ReplacePagesModal.vue'
import type { ComicDetail } from '@/types'

/**
 * 本子详情页 —— 编排封面轮播 / 元数据 / 操作栏 / 章节目录 / 页面索引。
 *
 * 章节摆放策略（对应 docs/agents/ui.md 的 Impeccable 设计）：
 * - 单章节（无 chapters / length<=1）：直接渲染整本 PageIndexGrid（每页平铺），体验不变；
 * - 多章节：详情页不再铺开几千页，只渲染「章节目录」（ChapterIndex，封面 + 章节信息），
 *   点某话进入章节子路由（/comic/:source/:id/chapter/:chapterId）看那话的页面索引。
 * 章节导航/增量渲染/继续阅读文案等业务逻辑收敛到 useChapterNavigation，本文件只保留
 * 数据加载、缓存轮询（useIntervalFn）、路由跳转等页面级编排。
 */

const route = useRoute()
const router = useRouter()
const store = useLibraryStore()
const { toast } = useToast()
const { canWrite } = useAuth()

const source = computed(() => String(route.params.source))

const sourceId = computed(() => String(route.params.sourceId))

// SWR 即时占位：若书架 Store 中已有该本子概要，立即构造初态渲染 Hero（封面、标题、作者等）
// 让 View Transition 精准咬合 Shared Cover Morph，彻底杜绝白屏/骨架屏二次闪烁
const cachedSummary = store.byId(source.value, sourceId.value)
const detail = ref<ComicDetail | null>(
  cachedSummary ? createPlaceholderDetail(cachedSummary) : null,
)
const loading = ref(!detail.value)
const caching = ref(false)
const editOpen = ref(false)
const appendOpen = ref(false)
const replaceOpen = ref(false)
let loadAbortController: AbortController | null = null

const lastRead = useLastRead(source, sourceId)
const {
  chapters,
  progressEl,
  visiblePages,
  remainingPages,
  showingRange,
  lastReadLabel,
  pageStep,
  loadMore,
} = useChapterNavigation(detail, lastRead)

const isMulti = computed(() => (chapters.value?.length ?? 0) > 1)

const cachePercent = computed(() => {
  if (!detail.value || detail.value.meta.page_count === 0) return 0
  return Math.round((detail.value.cached_pages / detail.value.meta.page_count) * 100)
})

/** T10：每话已本地缓存的页数（chapterId -> cachedPages），喂给章节目录卡片。 */
const chapterCache = computed(() => {
  const cache: Record<string, number> = {}
  for (const page of detail.value?.meta.pages ?? []) {
    if (!page.chapter) continue
    cache[page.chapter] = (cache[page.chapter] ?? 0) + (page.cached ? 1 : 0)
  }
  return cache
})

// 在主线程与首屏关键资产加载空闲时后台预热阅读器视图组件，避免混入初始关键请求链
useIdlePrefetch(() => import('@/views/ReaderView.vue'))

onMounted(() => {
  void load()
})

// 同组件跨漫画跳转时重新以 SWR 占位并重新拉取详情
watch(
  () => [source.value, sourceId.value],
  () => {
    const summary = store.byId(source.value, sourceId.value)
    detail.value = summary ? createPlaceholderDetail(summary) : null
    loading.value = !detail.value
    void load()
  },
)

onBeforeUnmount(() => {
  if (loadAbortController) {
    loadAbortController.abort()
    loadAbortController = null
  }
})

async function load(silent = false) {
  if (loadAbortController) {
    loadAbortController.abort()
  }
  const controller = new AbortController()
  loadAbortController = controller

  // SWR：若已有详情数据且非显式重载，不闪现骨架屏
  if (!silent && !detail.value) loading.value = true
  try {
    const data = await api.detail(source.value, sourceId.value, { signal: controller.signal })
    if (controller.signal.aborted) return
    detail.value = data

    // 预热目标阅读页的原图资源（浏览器内存/磁盘缓存），读者点击「继续阅读」时秒出
    const pageCount = detail.value.meta.page_count ?? 0
    if (pageCount > 0) {
      const targetPage = progressEl.value || 1
      const preloadImg = new Image()
      preloadImg.src = pageFileUrl(source.value, sourceId.value, targetPage)
    }

    // 若尚未完全缓存或后台有任务在运行，启动前端就地状态轮询
    const job = await api.cacheJob(source.value, sourceId.value, { signal: controller.signal })
    if (controller.signal.aborted) return

    if (job.running) caching.value = true
    if (!detail.value.cache_complete && detail.value.cached_pages < detail.value.meta.page_count) {
      startProgressPolling()
    } else if (job.running) {
      startProgressPolling()
    }
  } catch (e) {
    if (controller.signal.aborted) return
    toast(e instanceof Error ? e.message : String(e), 'error')
    router.replace('/')
  } finally {
    if (loadAbortController === controller) {
      if (!silent) loading.value = false
      loadAbortController = null
    }
  }
}

/* 缓存进度轮询：缓存进行时就地更新每页 cached 标记，绝不触碰已有图片与网络连接 */
const { pause: pauseProgressPolling, resume: resumeProgressPolling } = useIntervalFn(
  async () => {
    try {
      const progress = await api.cacheProgress(source.value, sourceId.value)
      if (detail.value) {
        detail.value.cached_pages = progress.cached
        detail.value.cache_complete = progress.complete

        // 前端就地标记已完成的页码，保证零 DOM 销毁、零图片重复加载、角标与进度秒级同步
        if (detail.value.meta?.pages) {
          for (const p of detail.value.meta.pages) {
            if (progress.complete || p.index <= progress.cached) {
              p.cached = true
            }
          }
        }
      }
      if (progress.complete) {
        caching.value = false
        if (detail.value?.meta?.pages) {
          for (const p of detail.value.meta.pages) {
            p.cached = true
          }
        }
        pauseProgressPolling()
      }
    } catch {
      /* the long-running request owns the error path */
    }
  },
  1000,
  { immediate: false },
)

function startProgressPolling() {
  pauseProgressPolling()
  resumeProgressPolling()
}

async function cacheAll() {
  if (!detail.value || caching.value) return
  caching.value = true
  startProgressPolling()
  try {
    const progress = await api.cacheAll(source.value, sourceId.value)
    detail.value.cached_pages = progress.cached
    detail.value.cache_complete = progress.complete
    if (detail.value.meta?.pages) {
      for (const p of detail.value.meta.pages) {
        if (progress.complete || p.index <= progress.cached) {
          p.cached = true
        }
      }
    }
    await store.load()
    toast(progress.complete ? '已全部缓存到本地' : '后台缓存进行中，进度会自动更新', 'info')
    if (progress.complete) {
      pauseProgressPolling()
    } else {
      resumeProgressPolling()
    }
  } catch (e) {
    pauseProgressPolling()
    toast(e instanceof Error ? e.message : String(e), 'error')
  } finally {
    caching.value = false
  }
}

async function removeComic() {
  // 危险确认已内联到 DetailActionBar（票据 01），这里只做真正的删除。
  if (!detail.value) return
  try {
    await store.remove(source.value, sourceId.value)
    toast('已从纸间移除')
    router.replace('/')
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  }
}

async function refreshMetadata() {
  try {
    const prevPageCount = detail.value?.meta.page_count ?? 0
    const prevChapterCount = chapters.value?.length ?? 0
    const result = await store.importComic({
      id: sourceId.value,
      source: source.value,
      prefetch_covers: 4,
      refresh: true,
    })
    await load()
    const nextPageCount = result.meta.page_count ?? 0
    const nextChapterCount = result.meta.chapters?.length ?? 0
    if (nextPageCount > prevPageCount || nextChapterCount > prevChapterCount) {
      const newChaps = nextChapterCount - prevChapterCount
      const newPages = nextPageCount - prevPageCount
      if (newChaps > 0) {
        toast(`已增量更新：新增 ${newChaps} 话（共 ${newPages} 页），旧缓存已保留`)
      } else {
        toast(`已增量更新：新增 ${newPages} 页，旧缓存已保留`)
      }
    } else {
      toast('资料已刷新，当前已是最新版本')
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  }
}

const { setActiveCover } = useCoverTransition()

function goBack() {
  setActiveCover(source.value, sourceId.value)
  router.replace({ name: 'library' })
}

/** 定位某个全局页码所属的话（多章节作品；单章节返回 null）。 */
function chapterIdForPage(page: number): string | null {
  const chs = chapters.value
  if (chs.length <= 1) return null
  return chs.find((c) => page >= c.start && page < c.start + c.page_count)?.id ?? chs[0]?.id ?? null
}

function startReading(page = progressEl.value || 1) {
  // 多章节作品从父详情的任何「直接进入」都走章节维度：带 ?chapter= 让阅读器
  // 只渲染当前话（比如 37 页），绝不一次把 7227 页铺进阅读器。
  const chapterId = chapterIdForPage(page)
  const path = chapterId
    ? `/comic/${source.value}/${sourceId.value}/read/${page}?chapter=${encodeURIComponent(chapterId)}`
    : `/comic/${source.value}/${sourceId.value}/read/${page}`
  router.push(path)
}
</script>

<template>
  <div class="detail-view container">
    <div v-if="loading" class="detail-loading">
      <div class="skeleton detail-skeleton" />
      <div class="skeleton meta-skeleton" />
    </div>

    <template v-else-if="detail">
      <div class="detail-hero surface">
        <button
          class="detail-back icon-btn"
          type="button"
          aria-label="返回书库"
          title="返回书库"
          @click="goBack"
        >
          <AppIcon name="arrow-left" size="sm" />
        </button>
        <CoverCarousel
          class="detail-carousel"
          :covers="detail.cover_paths"
          :title="detail.meta.title"
        />
        <MetadataPanel class="detail-meta" :meta="detail.meta" />
      </div>

      <DetailActionBar
        :title="detail.meta.title"
        :last-read="progressEl"
        :last-read-label="lastReadLabel"
        :cache-percent="cachePercent"
        :caching="caching"
        :cache-complete="detail.cache_complete"
        :cached-pages="detail.cached_pages"
        :page-count="detail.meta.page_count"
        :can-write="canWrite"
        :source="source"
        :custom-pages="detail.meta.custom_pages"
        @start-reading="startReading"
        @cache-all="cacheAll"
        @refresh-metadata="refreshMetadata"
        @remove-comic="removeComic"
        @edit-metadata="editOpen = true"
        @append-pages="appendOpen = true"
        @replace-pages="replaceOpen = true"
      />

      <ChapterIndex
        v-if="isMulti"
        :source="source"
        :source-id="sourceId"
        :chapters="chapters"
        :chapter-cache="chapterCache"
        :running="caching"
      />

      <PageIndexGrid
        v-else
        :source="source"
        :source-id="sourceId"
        :pages="visiblePages"
        :remaining-pages="remainingPages"
        :page-step="pageStep"
        :showing-range="showingRange"
        @load-more="loadMore"
      />

      <EditMetadataModal
        :open="editOpen"
        :meta="detail.meta"
        @cancel="editOpen = false"
        @saved="
          () => {
            editOpen = false
            load(true)
          }
        "
      />

      <AppendPagesModal
        v-if="source === 'local'"
        :open="appendOpen"
        :meta="detail.meta"
        @cancel="appendOpen = false"
        @appended="
          () => {
            appendOpen = false
            load(true)
          }
        "
      />

      <ReplacePagesModal
        :open="replaceOpen"
        :meta="detail.meta"
        @cancel="replaceOpen = false"
        @replaced="
          () => {
            replaceOpen = false
            load(true)
            store.load()
          }
        "
      />
    </template>
  </div>
</template>

<style scoped>
.detail-view {
  position: relative;
  isolation: isolate;
  overflow-x: clip;
  padding-block: var(--space-6) var(--space-10);
}

.detail-hero,
.detail-loading,
:deep(.detail-actions),
:deep(.chapter-index),
:deep(.page-index-grid) {
  position: relative;
  z-index: 1;
}

.detail-back {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  z-index: 2;
}

.detail-loading {
  display: grid;
  gap: var(--space-5);
}

.detail-skeleton {
  height: 30rem;
}

.meta-skeleton {
  height: 14rem;
}

.detail-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(18rem, 0.88fr);
  align-items: center;
  overflow: hidden;
  padding: var(--space-5);
}

.detail-carousel {
  min-width: 0;
}

.detail-meta {
  padding: var(--space-5);
  border-left: 1px solid var(--line);
}

@media (max-width: 980px) {
  .detail-hero {
    grid-template-columns: 1fr;
  }

  .detail-meta {
    border-left: 0;
    border-top: 1px solid var(--line);
  }
}
</style>

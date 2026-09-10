<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api, pageFileUrl } from '@/api/client'
import { useLastRead } from '@/composables/useLastRead'
import {
  getDetailScrollPosition,
  setDetailScrollPosition,
  useChapterNavigation,
} from '@/composables/useChapterNavigation'
import { useIdlePrefetch } from '@/composables/useIdlePrefetch'
import { useLibraryStore, createPlaceholderDetail } from '@/stores/library'
import { useToast } from '@/composables/useToast'
import { useCoverTransition } from '@/composables/useCoverTransition'
import { useAuth } from '@/composables/useAuth'
import { useOfflineSync } from '@/composables/useOfflineSync'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { useChapterCache } from '@/composables/useChapterCache'
import { useHierarchicalNavigation } from '@/composables/useHierarchicalNavigation'
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
const { canWrite, userId } = useAuth()
const { isOnline } = useOfflineSync()

const source = computed(() => String(route.params.source))

const sourceId = computed(() => String(route.params.sourceId))

// SWR 即时占位：若书架 Store 中已有完整缓存或概要，立即构造初态渲染
// 让 View Transition 精准咬合，彻底杜绝白屏/骨架屏二次闪烁与重复 JSON 解析
const cachedSummary = store.byId(source.value, sourceId.value)
const existingDetail = store.getDetail(source.value, sourceId.value)
const detail = ref<ComicDetail | null>(
  existingDetail ?? (cachedSummary ? createPlaceholderDetail(cachedSummary) : null),
)
const loading = ref(!detail.value)
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
  lastReadChapter,
  pageStep,
  canCollapse,
  chapterForPage,
  loadMore,
  loadAll,
  collapse,
} = useChapterNavigation(detail, lastRead)

const {
  caching,
  runningChapterId,
  syncJobState,
  cacheAll,
  cacheChapter: handleCacheChapter,
  onPageCached,
} = useChapterCache({
  source,
  sourceId,
  detail,
  chapters,
  onRefresh: () => load(true, true),
})

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

function restoreScrollPosition() {
  const key = `${source.value}/${sourceId.value}`
  const saved = getDetailScrollPosition(key)
  if (saved !== undefined && saved > 0) {
    nextTick(() => {
      window.scrollTo({ top: saved, behavior: 'instant' })
    })
  }
}

onBeforeRouteLeave((to) => {
  if (to.name === 'comic-chapter' || to.name === 'reader') {
    setDetailScrollPosition(`${source.value}/${sourceId.value}`, window.scrollY)
  }
})

onMounted(() => {
  restoreScrollPosition()
  void load()
})

// 同组件跨漫画跳转时重新以 SWR 占位并重新拉取详情
watch(
  () => [source.value, sourceId.value],
  () => {
    const summary = store.byId(source.value, sourceId.value)
    const existing = store.getDetail(source.value, sourceId.value)
    detail.value = existing ?? (summary ? createPlaceholderDetail(summary) : null)
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

const { lastLibraryEvent } = useSystemEvents()

watch(lastLibraryEvent, (event) => {
  if (!event) return
  if (
    (!event.source || event.source === source.value) &&
    (!event.source_id || event.source_id === sourceId.value)
  ) {
    // 收藏与翻页等轻量状态变动由各模块就地消化，不无谓发起全书大 JSON 重拉取
    if (event.action === 'favorite_changed') {
      if (detail.value?.meta && typeof event.favorite === 'boolean') {
        detail.value.meta.favorite = event.favorite
      }
      return
    }
    if (event.action === 'reading_progress_changed') {
      return
    }
    void load(true, true)
  }
})

async function load(silent = false, bypassCache = false) {
  if (loadAbortController) {
    loadAbortController.abort()
  }
  const controller = new AbortController()
  loadAbortController = controller

  // SWR：若已有详情数据且非显式重载，不闪现骨架屏
  if (!silent && !detail.value) loading.value = true
  try {
    const data = await api.detail(source.value, sourceId.value, {
      signal: controller.signal,
      bypassCache,
    })
    if (controller.signal.aborted) return
    detail.value = data
    store.setDetail(data, userId.value)

    // 预热目标阅读页的原图资源（浏览器内存/磁盘缓存），读者点击「继续阅读」时秒出
    const pageCount = detail.value.meta.page_count ?? 0
    if (pageCount > 0) {
      const targetPage = progressEl.value || 1
      const preloadImg = new Image()
      preloadImg.src = pageFileUrl(source.value, sourceId.value, targetPage)
    }

    // 严格任务驱动轮询（ADR 0010）：仅在后台有任务在运行时才开启轮询，静默状态绝不空转
    const job = await api.cacheJob(source.value, sourceId.value, { signal: controller.signal })
    if (controller.signal.aborted) return

    syncJobState(job)
  } catch (e) {
    if (controller.signal.aborted) return

    // 离线容错降级：优先命中本地 IndexedDB 或书架概要占位
    const offlineDetail = await store.getOrFetchOfflineDetail(
      source.value,
      sourceId.value,
      userId.value,
    )
    const summary = store.byId(source.value, sourceId.value)
    const fallback = offlineDetail || (summary ? createPlaceholderDetail(summary) : null)

    if (fallback) {
      detail.value = fallback
      return
    }

    toast(e instanceof Error ? e.message : String(e), 'error')
    router.replace('/')
  } finally {
    if (loadAbortController === controller) {
      if (!silent) loading.value = false
      loadAbortController = null
    }
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
const { goUpFromDetail } = useHierarchicalNavigation()

function goBack() {
  setActiveCover(source.value, sourceId.value)
  goUpFromDetail(source.value, sourceId.value)
}

function startReading(page = progressEl.value || 1) {
  // 多章节作品从父详情的任何「直接进入」都走章节维度：带 ?chapter= 让阅读器
  // 只渲染当前话（比如 37 页），绝不一次把 7227 页铺进阅读器。
  const chapterId = chapterForPage(page)
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
        :can-write="canWrite && isOnline && !store.isOffline"
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
        :running-chapter-id="runningChapterId"
        :initial-visible-chapter="lastReadChapter?.index"
        @cache-chapter="handleCacheChapter"
      />

      <PageIndexGrid
        v-else
        :source="source"
        :source-id="sourceId"
        :pages="visiblePages"
        :remaining-pages="remainingPages"
        :page-step="pageStep"
        :showing-range="showingRange"
        :can-collapse="canCollapse"
        @page-cached="onPageCached"
        @load-more="loadMore"
        @load-all="loadAll"
        @collapse="collapse"
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

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pageFileUrl } from '@/api/client'
import { useLastRead } from '@/composables/useLastRead'
import { useChapterNavigation } from '@/composables/useChapterNavigation'
import { useIdlePrefetch } from '@/composables/useIdlePrefetch'
import { useToast } from '@/composables/useToast'
import { useLibraryStore } from '@/stores/library'
import { useAuth } from '@/composables/useAuth'
import { useOfflineSync } from '@/composables/useOfflineSync'
import { useChapterCache } from '@/composables/useChapterCache'
import { useComicDetail } from '@/composables/useComicDetail'
import { useComicDetailActions } from '@/composables/useComicDetailActions'
import CoverCarousel from '@/components/CoverCarousel.vue'
import AppButton from '@/components/AppButton.vue'
import { calculateProgressPercent } from '@/utils/progress'

import DetailActionBar from '@/components/detail/DetailActionBar.vue'
import ChapterIndex from '@/components/detail/ChapterIndex.vue'
import MetadataPanel from '@/components/MetadataPanel.vue'
import PageIndexGrid from '@/components/detail/PageIndexGrid.vue'
import EditMetadataModal from '@/components/detail/EditMetadataModal.vue'
import AppendPagesModal from '@/components/detail/AppendPagesModal.vue'
import ReplacePagesModal from '@/components/detail/ReplacePagesModal.vue'
import type { CacheJob } from '@/types'

/**
 * 本子详情页 —— 编排封面轮播 / 元数据 / 操作栏 / 章节目录 / 页面索引。
 *
 * 遵循 docs/agents/frontend.md 规范：
 * - 视图轻量化（View Thinness ≤150 行）；
 * - 页面只做编排，状态与计算下沉至 composables；
 * - 契约自解释与顶层精准解构。
 */
const route = useRoute()
const router = useRouter()
const store = useLibraryStore()
const { toast } = useToast()
const { canWrite } = useAuth()
const { isOnline } = useOfflineSync()

const source = computed(() => String(route.params.source))
const sourceId = computed(() => String(route.params.sourceId))

const lastRead = useLastRead(source, sourceId)

// 声明 syncJobState 委托，解耦 useComicDetail 与 useChapterCache 的初始化依赖
let syncJobStateDelegate: ((job: CacheJob) => void) | undefined

const { detail, loading, load } = useComicDetail({
  source,
  sourceId,
  onLoaded: (data) => {
    const pageCount = data.meta.page_count ?? 0
    if (pageCount > 0) {
      const targetPage = progressEl.value || 1
      const preloadImg = new Image()
      preloadImg.src = pageFileUrl(source.value, sourceId.value, targetPage)
    }
  },
  onSyncJobState: (job) => syncJobStateDelegate?.(job),
  onError: (err) => {
    toast(err instanceof Error ? err.message : String(err), 'error')
    router.replace('/')
  },
})

const {
  chapters,
  chapterCache,
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
syncJobStateDelegate = syncJobState

const {
  editOpen,
  appendOpen,
  replaceOpen,
  restoreScrollPosition,
  removeComic,
  refreshMetadata,
  goBack,
  startReading,
} = useComicDetailActions({
  source,
  sourceId,
  detail,
  chapters,
  progressEl,
  chapterForPage,
  load,
})

const isMulti = computed(() => (chapters.value?.length ?? 0) > 1)

const cachePercent = computed(() => {
  if (!detail.value) return 0
  return calculateProgressPercent(detail.value.cached_pages, detail.value.meta.page_count)
})

useIdlePrefetch(() => import('@/views/ReaderView.vue'))

onMounted(() => {
  restoreScrollPosition()
  void load()
})
</script>

<template>
  <div class="detail-view container">
    <div v-if="loading" class="detail-loading">
      <div class="skeleton detail-skeleton" />
      <div class="skeleton meta-skeleton" />
    </div>

    <template v-else-if="detail">
      <div class="detail-hero surface">
        <AppButton
          class="detail-back"
          shape="circle"
          variant="ghost"
          size="md"
          icon="arrow-left"
          aria-label="返回书库"
          title="返回书库"
          @click="goBack"
        />
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

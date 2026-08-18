<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useIntervalFn } from '@vueuse/core'
import { api } from '@/api/client'
import { useLastRead } from '@/composables/useLastRead'
import { useLibraryStore } from '@/stores/library'
import { useToast } from '@/composables/useToast'
import CoverCarousel from '@/components/CoverCarousel.vue'
import DetailActionBar from '@/components/detail/DetailActionBar.vue'
import MetadataPanel from '@/components/MetadataPanel.vue'
import PageIndexGrid from '@/components/detail/PageIndexGrid.vue'
import type { ComicDetail } from '@/types'

/**
 * 本子详情页 —— 编排封面轮播 / 元数据 / 操作栏 / 页面索引。
 * 操作栏与页索引已在 components/detail/ 下沉，本文件只保留：
 * 数据加载、缓存轮询（useIntervalFn）、阅读记录（useLastRead）等业务编排。
 */

const route = useRoute()
const router = useRouter()
const store = useLibraryStore()
const { toast } = useToast()

const source = computed(() => String(route.params.source))
const sourceId = computed(() => String(route.params.sourceId))
const detail = ref<ComicDetail | null>(null)
const loading = ref(true)
const caching = ref(false)
const PAGE_STEP = 48
const visiblePageCount = ref(PAGE_STEP)

const lastRead = useLastRead(source, sourceId)
const progressEl = computed(() =>
  lastRead.value >= 1 && lastRead.value <= (detail.value?.meta.page_count ?? 0)
    ? lastRead.value
    : 0,
)

const cachePercent = computed(() => {
  if (!detail.value || detail.value.meta.page_count === 0) return 0
  return Math.round((detail.value.cached_pages / detail.value.meta.page_count) * 100)
})

const visiblePages = computed(() => {
  if (!detail.value) return []
  return detail.value.meta.pages.slice(0, visiblePageCount.value)
})

const remainingPages = computed(() => {
  if (!detail.value) return 0
  return Math.max(0, detail.value.meta.page_count - visiblePageCount.value)
})

const showingRange = computed(() => {
  if (!detail.value) return ''
  const end = Math.min(visiblePageCount.value, detail.value.meta.page_count)
  return `已显示 ${end} / ${detail.value.meta.page_count} 页`
})

onMounted(load)

function loadMore() {
  if (!detail.value) return
  visiblePageCount.value = Math.min(
    detail.value.meta.page_count,
    visiblePageCount.value + PAGE_STEP,
  )
}

async function load() {
  loading.value = true
  try {
    detail.value = await api.detail(source.value, sourceId.value)
    // If a background import/prefetch is running (import/cache-all now return
    // immediately), pick up live progress without the user having to click.
    const job = await api.cacheJob(source.value, sourceId.value)
    if (job.running) startProgressPolling()
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
    router.replace('/')
  } finally {
    loading.value = false
  }
}

/* 缓存进度轮询：缓存动作开始时 resume，结束/卸载时自动 pause */
const { pause: pauseProgressPolling, resume: resumeProgressPolling } = useIntervalFn(
  async () => {
    try {
      const progress = await api.cacheProgress(source.value, sourceId.value)
      if (detail.value) {
        detail.value.cached_pages = progress.cached
        detail.value.cache_complete = progress.complete
      }
    } catch {
      /* the long-running request owns the error path */
    }
  },
  1200,
  { immediate: false },
)

function startProgressPolling() {
  // restart from a clean slate each cache run
  pauseProgressPolling()
  resumeProgressPolling()
}

async function cacheAll() {
  if (!detail.value || caching.value) return
  caching.value = true
  startProgressPolling()
  try {
    // cacheAll returns immediately now; the heavy download runs in background
    // and keeps updating via the polling above until complete.
    const progress = await api.cacheAll(source.value, sourceId.value)
    detail.value.cached_pages = progress.cached
    detail.value.cache_complete = progress.complete
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

async function refreshMetadata() {
  try {
    await store.importComic({
      id: sourceId.value,
      source: source.value,
      prefetch_covers: 4,
      refresh: true,
    })
    toast('资料已从远端刷新，页面文件继续保留')
    await load()
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  }
}

async function removeComic() {
  if (!detail.value) return
  const ok = window.confirm(`删除《${detail.value.meta.title}》的本地缓存？`)
  if (!ok) return
  try {
    await store.remove(source.value, sourceId.value)
    toast('已从纸间移除')
    router.replace('/')
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  }
}

function goBack() {
  router.replace({ name: 'library' })
}

function startReading(page = progressEl.value || 1) {
  router.push(`/comic/${source.value}/${sourceId.value}/read/${page}`)
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
        <button class="detail-back icon-btn" type="button" aria-label="返回书库" @click="goBack">
          <span aria-hidden="true">←</span>
        </button>
        <CoverCarousel
          class="detail-carousel"
          :covers="detail.cover_paths"
          :title="detail.meta.title"
        />
        <MetadataPanel class="detail-meta" :meta="detail.meta" />
      </div>

      <DetailActionBar
        :last-read="progressEl"
        :cache-percent="cachePercent"
        :caching="caching"
        :cache-complete="detail.cache_complete"
        :cached-pages="detail.cached_pages"
        :page-count="detail.meta.page_count"
        @start-reading="startReading"
        @cache-all="cacheAll"
        @refresh-metadata="refreshMetadata"
        @remove-comic="removeComic"
      />

      <PageIndexGrid
        :source="source"
        :source-id="sourceId"
        :pages="visiblePages"
        :remaining-pages="remainingPages"
        :page-step="PAGE_STEP"
        :showing-range="showingRange"
        @load-more="loadMore"
      />
    </template>
  </div>
</template>

<style scoped>
.detail-view {
  padding-block: var(--space-6) var(--space-10);
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

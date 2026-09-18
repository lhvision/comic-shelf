<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { useOfflineSync } from '@/composables/useOfflineSync'
import { useLastRead } from '@/composables/useLastRead'
import { useChapterNavigation } from '@/composables/useChapterNavigation'
import { useChapterPageInfo } from '@/composables/useChapterPageInfo'
import { useChapterManagement } from '@/composables/useChapterManagement'
import { useIdlePrefetch } from '@/composables/useIdlePrefetch'
import { useToast } from '@/composables/useToast'
import { useChapterCache } from '@/composables/useChapterCache'
import { useComicDetail } from '@/composables/useComicDetail'
import { useComicDetailWebMCP } from '@/composables/useComicDetailWebMCP'
import { api } from '@/api/client'
import ChapterSwitcher from '@/components/detail/ChapterSwitcher.vue'
import PageIndexGrid from '@/components/detail/PageIndexGrid.vue'
import CacheProgress from '@/components/CacheProgress.vue'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'
import AppDropdown from '@/components/AppDropdown.vue'
import AppendPagesModal from '@/components/detail/AppendPagesModal.vue'
import ReplacePagesModal from '@/components/detail/ReplacePagesModal.vue'
import { useLibraryStore } from '@/stores/library'
import type { CacheJob } from '@/types'

/** 章节子路由详情 —— 一本多话作品的「单个话」页面索引 */
const route = useRoute()
const router = useRouter()
const store = useLibraryStore()
const { toast } = useToast()
const { canWrite } = useAuth()
const { isOnline } = useOfflineSync()

const source = computed(() => (route.params.source as string) || 'jm')
const sourceId = computed(() => (route.params.sourceId as string) || '')
const chapterId = computed(() => (route.params.chapterId as string) || '')
const lastRead = useLastRead(source, sourceId)

// 声明 syncJobState 委托，解耦 useComicDetail 与 useChapterCache 的初始化依赖
let syncJobStateDelegate: ((job: CacheJob) => void) | undefined

const { detail, loading, load } = useComicDetail({
  source,
  sourceId,
  onLoaded: () => {
    setChapterById(chapterId.value)
    if (!activeChapter.value) router.replace(`/comic/${source.value}/${sourceId.value}`)
  },
  onFallback: () => setChapterById(chapterId.value),
  onSyncJobState: (job) => syncJobStateDelegate?.(job),
  onError: (e) => {
    toast(e instanceof Error ? e.message : String(e), 'error')
    router.replace(`/comic/${source.value}/${sourceId.value}`)
  },
})

const {
  chapters,
  progressEl,
  activeChapterLabel,
  visiblePages,
  remainingPages,
  showingRange,
  pageStep,
  canCollapse,
  loadMore,
  loadAll,
  collapse,
  setChapterById,
} = useChapterNavigation(detail, lastRead)

const activeChapterRef = computed(
  () => chapters.value.find((c) => c.id === chapterId.value) ?? null,
)

const { caching, runningChapterId, syncJobState, cacheChapter, onPageCached } = useChapterCache({
  source,
  sourceId,
  detail,
  chapters,
  activeChapterId: computed(() => activeChapterRef.value?.id),
  onRefresh: () => load(true, true),
})
syncJobStateDelegate = syncJobState

const {
  activeChapter,
  prevChapter,
  nextChapter,
  activeChapterCached,
  activeChapterTotal,
  chapterRange,
  isCurrentChapterCaching,
  readChapterLabel,
  cacheCurrentChapter,
  goToAlbum,
  goToChapter,
  startReadingChapter,
  goPrev,
  goNext,
} = useChapterPageInfo({
  source,
  sourceId,
  chapterId,
  chapters,
  detail,
  progressEl,
  caching,
  runningChapterId,
  cacheChapter,
})

const {
  editOpen,
  chapterTitleInput,
  savingTitle,
  removeOpen,
  ackRemove,
  removing,
  replaceOpen,
  appendOpen,
  chapterMoreOptions,
  onChapterMoreSelect,
  saveChapterTitle,
  confirmRemoveChapter,
} = useChapterManagement({
  source,
  sourceId,
  activeChapter,
  onDetailUpdated: (updated) => (detail.value = updated),
})

watch(
  chapterId,
  (newId, oldId) => {
    setChapterById(chapterId.value)
    if (oldId !== undefined && newId !== oldId) void load(true)
  },
  { immediate: true },
)

useComicDetailWebMCP({
  source,
  sourceId,
  detail,
  chapters,
  lastRead,
  router,
  cacheChapter,
  activeChapterId: computed(() => activeChapter.value?.id),
  toggleFavorite: async () => {
    if (detail.value) {
      const nextFav = !detail.value.meta.favorite
      detail.value.meta.favorite = nextFav
      await api.setFavorite(source.value, sourceId.value, nextFav)
    }
  },
})

useIdlePrefetch(() => import('@/views/ReaderView.vue'))

onMounted(() => {
  void load()
})
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
          <div class="chapter-head-title-row">
            <AppButton
              class="chapter-back"
              shape="circle"
              variant="ghost"
              size="md"
              icon="arrow-left"
              aria-label="返回本子详情"
              title="返回本子详情"
              @click="goToAlbum"
            />
            <p class="eyebrow">第 {{ activeChapter.index }} 話</p>
          </div>

          <div class="chapter-head-status">
            <CacheProgress
              :cached="activeChapterCached"
              :total="activeChapterTotal"
              :running="isCurrentChapterCaching"
            />
          </div>
        </div>

        <div class="chapter-head-main">
          <h1 :title="activeChapter.title || `第 ${activeChapter.index} 話`">
            {{ activeChapter.title || `第 ${activeChapter.index} 話` }}
          </h1>
          <p class="chapter-head-meta">
            {{ activeChapter.index }} / {{ chapters.length }} 话 · {{ activeChapter.page_count }} 页
            · {{ chapterRange }} · 本子「{{ detail.meta.title }}」
          </p>
        </div>

        <div class="chapter-head-actions">
          <AppButton
            class="action-btn action-btn-read"
            variant="primary"
            size="sm"
            type="button"
            :title="readChapterLabel"
            @click="startReadingChapter"
          >
            {{ readChapterLabel }}
          </AppButton>

          <AppButton
            v-if="activeChapterCached < activeChapterTotal"
            class="action-btn action-btn-cache"
            variant="secondary"
            size="sm"
            type="button"
            :disabled="caching"
            :title="
              isCurrentChapterCaching
                ? '本话缓存进行中...'
                : caching
                  ? '已有其他缓存任务在进行中'
                  : '离线缓存本话所有画页'
            "
            @click="cacheCurrentChapter"
          >
            {{ isCurrentChapterCaching ? '缓存中…' : caching ? '排队中…' : '缓存本话' }}
          </AppButton>

          <div v-if="canWrite && isOnline && !store.isOffline" class="chapter-mgmt-group">
            <AppDropdown :options="chapterMoreOptions" align="end" @select="onChapterMoreSelect">
              <template #trigger="{ open }">
                <AppButton
                  variant="ghost"
                  size="sm"
                  shape="square"
                  class="more-trigger"
                  :class="{ 'is-open': open }"
                  type="button"
                  icon="more"
                  aria-label="更多章节操作"
                  title="更多章节操作"
                />
              </template>
            </AppDropdown>
          </div>
        </div>

        <div v-if="chapters.length > 1" class="chapter-pager">
          <AppButton
            class="pager-nav-btn pager-prev-btn"
            variant="ghost"
            size="sm"
            type="button"
            icon="arrow-left"
            :disabled="!prevChapter"
            aria-label="上一话"
            title="上一话 (快捷键 [ )"
            @click="goPrev"
          >
            <span class="pager-btn-text">上一话</span>
          </AppButton>

          <ChapterSwitcher
            class="pager-tabs"
            :chapters="chapters"
            :active-id="activeChapter.id"
            in-pager
            @change="goToChapter"
          />

          <AppButton
            class="pager-nav-btn pager-next-btn"
            variant="ghost"
            size="sm"
            type="button"
            icon="arrow-right"
            icon-position="right"
            :disabled="!nextChapter"
            aria-label="下一话"
            title="下一话 (快捷键 ] )"
            @click="goNext"
          >
            <span class="pager-btn-text">下一话</span>
          </AppButton>
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
        :can-collapse="canCollapse"
        @page-cached="onPageCached"
        @load-more="loadMore"
        @load-all="loadAll"
        @collapse="collapse"
      />

      <!-- 修改章节名称弹窗 -->
      <Modal
        :open="editOpen"
        :title="`编辑第 ${activeChapter.index} 话名称`"
        @cancel="editOpen = false"
      >
        <div class="edit-chap-form">
          <label class="form-label" for="chap-title-input">章节名称</label>
          <input
            id="chap-title-input"
            v-model="chapterTitleInput"
            class="form-input"
            type="text"
            placeholder="例如：第 1 话 · 初始篇"
            maxlength="100"
            @keydown.enter.prevent="saveChapterTitle"
          />
        </div>

        <template #footer>
          <AppButton variant="ghost" size="sm" type="button" @click="editOpen = false">
            取消
          </AppButton>
          <AppButton
            variant="primary"
            size="sm"
            type="button"
            :loading="savingTitle"
            @click="saveChapterTitle"
          >
            保存
          </AppButton>
        </template>
      </Modal>

      <!-- 删除章节二次确认弹窗 -->
      <Modal
        :open="removeOpen"
        :title="`删除《${activeChapter.title || `第 ${activeChapter.index} 话`}》？`"
        @cancel="removeOpen = false"
      >
        <p class="remove-copy">
          该操作将永久删除本章节所有本地页面（共
          {{ activeChapter.page_count }} 页）以及该话专属缩略图。
          删除后后续章节的序号与全书页码将自动单调重排，此操作不可撤销。
        </p>

        <label class="remove-ack">
          <input v-model="ackRemove" type="checkbox" />
          <span>我已了解此操作不可撤销，确认永久删除该话所有页面</span>
        </label>

        <template #footer>
          <AppButton variant="ghost" size="sm" type="button" @click="removeOpen = false">
            取消
          </AppButton>
          <AppButton
            variant="danger"
            size="sm"
            type="button"
            :disabled="!ackRemove"
            :loading="removing"
            @click="confirmRemoveChapter"
          >
            确认删除
          </AppButton>
        </template>
      </Modal>

      <!-- 重新装订本话弹窗 -->
      <ReplacePagesModal
        :open="replaceOpen"
        :meta="detail.meta"
        :initial-chapter-id="activeChapter.id"
        @cancel="replaceOpen = false"
        @replaced="
          () => {
            replaceOpen = false
            load(true)
          }
        "
      />

      <!-- 在本话追加画页弹窗 -->
      <AppendPagesModal
        :open="appendOpen"
        :meta="detail.meta"
        :initial-chapter-id="activeChapter.id"
        initial-append-type="current"
        @cancel="appendOpen = false"
        @appended="
          () => {
            appendOpen = false
            load(true)
          }
        "
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
  gap: var(--space-3-5);
  padding: var(--space-5);
}

.chapter-head-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  min-width: 0;
}

.chapter-head-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2-5);
  min-width: 0;
}

.chapter-head-title-row .eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.chapter-head-status {
  flex-shrink: 0;
}

.chapter-head-main {
  display: grid;
  gap: var(--space-1);
}

.chapter-head-main h1 {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  line-height: var(--leading-tight);
  color: var(--ink-0);
  word-break: break-word;
}

.chapter-head-meta {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  line-height: 1.4;
  word-break: break-word;
}

.chapter-head-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2-5);
  flex-wrap: wrap;
}

.chapter-mgmt-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.more-trigger {
  min-width: 2.25rem;
}

.edit-chap-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--ink-2);
}

.form-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-0);
  font-family: inherit;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.remove-copy {
  color: var(--ink-1);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.remove-ack {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  margin-top: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  font-size: var(--text-xs);
  color: var(--ink-1);
  cursor: pointer;
}

.chapter-pager {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  border-top: 1px solid var(--line);
  margin-top: var(--space-1);
  padding-top: var(--space-3);
  min-width: 0;
}

.pager-tabs {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
}

@media (max-width: 680px) {
  .chapter-head {
    padding: var(--space-3-5);
    gap: var(--space-3);
  }

  .chapter-head-actions {
    display: flex;
    align-items: stretch;
    gap: var(--space-2);
    width: 100%;
  }

  .action-btn {
    flex: 1 1 0;
    min-width: 0;
    min-height: 2.75rem; /* 44px 移动端触控底线 */
    font-size: var(--text-sm);
    justify-content: center;
  }

  .chapter-mgmt-group {
    margin-left: 0;
    flex-shrink: 0;
  }

  .more-trigger {
    min-width: 2.75rem; /* 44px 移动端触控底线 */
    min-height: 2.75rem; /* 44px 移动端触控底线 */
  }

  .chapter-head-main h1 {
    font-size: var(--text-lg);
  }

  .chapter-head-meta {
    font-size: var(--text-caption);
  }

  .chapter-pager {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: var(--space-2);
  }

  .pager-btn-text {
    display: none; /* 移动端隐藏翻页字样，保留图标与 44px 正方形触控热区 */
  }

  .pager-nav-btn {
    flex: 0 0 2.75rem;
    min-width: 2.75rem;
    min-height: 2.75rem; /* 44px 移动端触控底线 */
    padding: 0;
    justify-content: center;
  }

  .pager-tabs {
    flex: 1 1 auto;
    min-width: 0;
    order: unset;
    width: auto;
  }
}
</style>

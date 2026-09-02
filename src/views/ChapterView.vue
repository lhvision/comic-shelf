<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { onClickOutside, useIntervalFn } from '@vueuse/core'
import { api } from '@/api/client'
import { useAuth } from '@/composables/useAuth'
import { useLastRead } from '@/composables/useLastRead'
import { useChapterNavigation } from '@/composables/useChapterNavigation'
import { useIdlePrefetch } from '@/composables/useIdlePrefetch'
import { useToast } from '@/composables/useToast'
import ChapterSwitcher from '@/components/detail/ChapterSwitcher.vue'
import PageIndexGrid from '@/components/detail/PageIndexGrid.vue'
import CacheProgress from '@/components/CacheProgress.vue'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppDropdown, { type DropdownOption } from '@/components/AppDropdown.vue'
import type { ComicDetail } from '@/types'

/**
 * 章节子路由详情 —— 一本多话作品的「单个话」页面索引。
 *
 * 设计（对应 docs/agents/ui.md + Impeccable 234 步）：
 * 多章节作品在详情页只摆「章节目录」（ChapterIndex），不铺开几千页；
 * 点某话进入本子路由，只渲染这一话的页面索引 + 章节头（标题/页数/上一话/下一话/本话缓存进度/章节管理）。
 * 阅读器沿用全局页码，因此本页 PageTile 仍链接全局页号。
 *
 * 遵守 docs/agents/frontend.md 规范：
 * - Composable（useChapterNavigation）解构至 setup 顶层，Ref 直接绑定模板；
 * - 视图只做编排，状态下沉。
 */
const route = useRoute()
const router = useRouter()
const { toast } = useToast()
const { canWrite } = useAuth()

const source = computed(() => (route.params.source as string) || 'jm')
const sourceId = computed(() => (route.params.sourceId as string) || '')
const chapterId = computed(() => (route.params.chapterId as string) || '')

const loading = ref(true)
const error = ref<string | null>(null)
const detail = ref<ComicDetail | null>(null)
const caching = ref(false)
let loadAbortController: AbortController | null = null

const editOpen = ref(false)
const chapterTitleInput = ref('')
const savingTitle = ref(false)

const removeOpen = ref(false)
const ackRemove = ref(false)
const removing = ref(false)

const chapterMoreOptions = computed<DropdownOption[]>(() => [
  {
    key: 'remove',
    label: '删除本话…',
    danger: true,
    hint: '不可撤销',
  },
])

function onChapterMoreSelect(option: DropdownOption) {
  if (option.key === 'remove') {
    requestRemoveChapter()
  }
}

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

const activeChapterCached = computed(() => {
  if (!detail.value || !activeChapter.value) return 0
  const ch = activeChapter.value
  let cached = 0
  for (const p of detail.value.meta?.pages ?? []) {
    if (p.index >= ch.start && p.index < ch.start + ch.page_count) {
      if (p.cached) cached++
    }
  }
  return cached
})

const activeChapterTotal = computed(() => activeChapter.value?.page_count ?? 0)

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

// 在主线程与首屏关键资产加载空闲时后台预热阅读器视图组件，避免混入初始关键请求链
useIdlePrefetch(() => import('@/views/ReaderView.vue'))

onMounted(() => {
  void load()
})

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
    setChapterById(chapterId.value)
    // 单章节或无此章节时回落详情页
    if (!activeChapter.value) {
      router.replace(`/comic/${source.value}/${sourceId.value}`)
      return
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
    router.replace(`/comic/${source.value}/${sourceId.value}`)
  } finally {
    if (loadAbortController === controller) {
      if (!silent) loading.value = false
      loadAbortController = null
    }
  }
}

/* 缓存进度轮询：若后台在预缓存/全量缓存，就地更新当前章节每页 cached 状态 */
let isPollingProgress = false
const { pause: pauseProgressPolling, resume: resumeProgressPolling } = useIntervalFn(
  async () => {
    if (isPollingProgress) return
    isPollingProgress = true
    try {
      const progress = await api.cacheProgress(source.value, sourceId.value)
      if (detail.value) {
        detail.value.cached_pages = Math.max(detail.value.cached_pages, progress.cached)
        detail.value.cache_complete = progress.complete

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
      /* transient */
    } finally {
      isPollingProgress = false
    }
  },
  1000,
  { immediate: false },
)

function startProgressPolling() {
  pauseProgressPolling()
  resumeProgressPolling()
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

function openEditModal() {
  chapterTitleInput.value = activeChapter.value?.title || ''
  editOpen.value = true
}

async function saveChapterTitle() {
  if (!activeChapter.value) return
  savingTitle.value = true
  try {
    detail.value = await api.updateChapter(
      source.value,
      sourceId.value,
      activeChapter.value.id,
      chapterTitleInput.value,
    )
    editOpen.value = false
    toast('章节名称已更新', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  } finally {
    savingTitle.value = false
  }
}

function requestRemoveChapter() {
  ackRemove.value = false
  removeOpen.value = true
}

async function confirmRemoveChapter() {
  if (!activeChapter.value) return
  removing.value = true
  const deletedTitle = activeChapter.value.title || `第 ${activeChapter.value.index} 话`
  try {
    await api.deleteChapter(source.value, sourceId.value, activeChapter.value.id)
    removeOpen.value = false
    toast(`已删除「${deletedTitle}」`, 'success')
    router.replace(`/comic/${source.value}/${sourceId.value}`)
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  } finally {
    removing.value = false
  }
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
          <div class="chapter-head-title-row">
            <button
              class="chapter-back icon-btn"
              type="button"
              aria-label="返回本子详情"
              title="返回本子详情"
              @click="goToAlbum"
            >
              <AppIcon name="arrow-left" size="sm" />
            </button>
            <p class="eyebrow">第 {{ activeChapter.index }} 話</p>
          </div>

          <div class="chapter-head-actions">
            <CacheProgress
              :cached="activeChapterCached"
              :total="activeChapterTotal"
              :running="caching"
            />

            <div v-if="canWrite" class="chapter-mgmt-group">
              <button
                class="btn btn-ghost btn-xs"
                type="button"
                title="修改本话名称"
                @click="openEditModal"
              >
                编辑章节
              </button>

              <AppDropdown :options="chapterMoreOptions" align="end" @select="onChapterMoreSelect">
                <template #trigger="{ open }">
                  <button
                    class="btn btn-ghost btn-xs more-trigger"
                    :class="{ 'is-open': open }"
                    type="button"
                    title="更多章节操作"
                  >
                    <AppIcon name="more" size="xs" />
                  </button>
                </template>
              </AppDropdown>
            </div>
          </div>
        </div>

        <h1 :title="activeChapter.title || `第 ${activeChapter.index} 話`">
          {{ activeChapter.title || `第 ${activeChapter.index} 話` }}
        </h1>
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
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.chapter-head-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chapter-head-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chapter-mgmt-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.btn-xs {
  padding: var(--space-1) var(--space-2-5);
  font-size: var(--text-xs);
  min-height: 1.75rem;
}

.more-menu {
  position: relative;
}

.more-trigger {
  min-width: 1.75rem;
  font-weight: bold;
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

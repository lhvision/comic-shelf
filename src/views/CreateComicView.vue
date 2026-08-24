<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useFileDialog, useDropZone } from '@vueuse/core'
import { api } from '@/api/client'
import { useLibraryStore } from '@/stores/library'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useUploadQueue } from '@/composables/useUploadQueue'
import TagManager from '@/components/form/TagManager.vue'
import CoverIndicesPicker from '@/components/form/CoverIndicesPicker.vue'
import type { LocalChapterInput } from '@/types'

interface StagedChapter {
  id: string
  title: string
  files: File[]
}

const router = useRouter()
const store = useLibraryStore()
const { canWrite } = useAuth()
const { toast } = useToast()
const { isUploading, progress, completedCount, totalCount, uploadFiles } = useUploadQueue()

onMounted(() => {
  if (!canWrite.value) {
    toast('访客模式下无法进入自建工坊，请先解锁馆长权限', 'error')
    router.replace('/')
  }
})

const mode = ref<'upload' | 'path'>('upload')
const isMulti = ref(false)

// Form fields
const slugId = ref('')
const title = ref('')
const works = ref('')
const authors = ref('自制')
const actors = ref('')
const uploader = ref('lhvision')
const description = ref('')
const tags = ref<string[]>([])
const serverPath = ref('')
const coverIndices = ref<number[]>([1, 2, 3, 4])
const submitting = ref(false)

// Staged chapters
const activeChapterIdx = ref(0)
const chapters = ref<StagedChapter[]>([{ id: 'ch1', title: '第 1 话', files: [] }])
const singleFiles = ref<File[]>([])

// DropZone & FileDialog via VueUse
const dropAreaRef = ref<HTMLElement | null>(null)

function naturalSortFiles(files: File[]): File[] {
  return [...files].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }),
  )
}

function stageFiles(rawList: File[]) {
  const list = rawList.filter((f) => /\.(jpe?g|png|webp|gif|avif|bmp)$/i.test(f.name))
  if (isMulti.value) {
    const ch = chapters.value[activeChapterIdx.value]
    if (ch) {
      ch.files = naturalSortFiles([...ch.files, ...list])
    }
  } else {
    singleFiles.value = naturalSortFiles([...singleFiles.value, ...list])
  }
}

const { open: openFileDialog, onChange: onFileDialogChange } = useFileDialog({
  multiple: true,
  accept: 'image/*',
  reset: true,
})

onFileDialogChange((files) => {
  if (files) stageFiles(Array.from(files))
})

const { isOverDropZone } = useDropZone(dropAreaRef, {
  onDrop: (files) => {
    if (files) stageFiles(files)
  },
})

function addChapter() {
  const nextIdx = chapters.value.length + 1
  chapters.value.push({
    id: `ch${nextIdx}`,
    title: `第 ${nextIdx} 话`,
    files: [],
  })
  activeChapterIdx.value = chapters.value.length - 1
}

function removeChapter(idx: number) {
  if (chapters.value.length <= 1) return
  chapters.value.splice(idx, 1)
  if (activeChapterIdx.value >= chapters.value.length) {
    activeChapterIdx.value = chapters.value.length - 1
  }
}

function clearCurrentStaged() {
  if (isMulti.value) {
    const current = chapters.value[activeChapterIdx.value]
    if (current) current.files = []
  } else {
    singleFiles.value = []
  }
}

const totalStagedFilesCount = computed(() => {
  if (!isMulti.value) return singleFiles.value.length
  return chapters.value.reduce((acc, ch) => acc + ch.files.length, 0)
})

function parseList(str: string): string[] {
  return str
    .split(/[/,，、]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

async function submit() {
  if (!title.value.trim()) {
    toast('请输入作品标题', 'error')
    return
  }

  if (mode.value === 'path') {
    if (!serverPath.value.trim()) {
      toast('请输入服务器目录路径', 'error')
      return
    }
    submitting.value = true
    try {
      const res = await api.importLocalPath({
        path: serverPath.value.trim(),
        id: slugId.value.trim() || undefined,
        title: title.value.trim(),
        works: parseList(works.value),
        authors: parseList(authors.value),
        actors: parseList(actors.value),
        tags: tags.value,
        description: description.value.trim(),
        uploader: uploader.value.trim() || '本地导入',
        cover_indices: coverIndices.value,
      })
      await store.load()
      toast('本地目录已收录', 'info')
      router.push(`/comic/${res.meta.source}/${res.meta.source_id}`)
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'error')
    } finally {
      submitting.value = false
    }
    return
  }

  // Upload mode
  if (totalStagedFilesCount.value === 0) {
    toast('请先选择或拖入图片文件', 'error')
    return
  }

  submitting.value = true
  try {
    const chapterInputs: LocalChapterInput[] = isMulti.value
      ? chapters.value.map((c) => ({ id: c.id, title: c.title }))
      : []

    // 1. Create base metadata
    const created = await api.createLocalComic({
      id: slugId.value.trim() || undefined,
      title: title.value.trim(),
      works: parseList(works.value),
      authors: parseList(authors.value),
      actors: parseList(actors.value),
      tags: tags.value,
      description: description.value.trim(),
      uploader: uploader.value.trim() || '自制',
      chapters: chapterInputs,
      cover_indices: coverIndices.value,
    })

    const sourceId = created.meta.source_id

    // 2. Upload files via controlled queue
    if (isMulti.value) {
      for (const ch of chapters.value) {
        if (ch.files.length > 0) {
          await uploadFiles(sourceId, ch.files, ch.id, ch.title)
        }
      }
    } else {
      await uploadFiles(sourceId, singleFiles.value, '', '')
    }

    await store.load()
    toast('自建图集已成功收录至纸间', 'info')
    router.push(`/comic/local/${sourceId}`)
  } catch (err) {
    toast(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push('/')
}
</script>

<template>
  <div class="create-view container">
    <header class="create-head surface">
      <button class="back-btn icon-btn" type="button" aria-label="返回书库" @click="goBack">
        ←
      </button>
      <div>
        <p class="eyebrow">Local Workshop / 自建工坊</p>
        <h1>收录自建图集与本地拆帧</h1>
      </div>
    </header>

    <div class="create-grid">
      <!-- Left Column: Staging / Upload zone -->
      <section class="staging-col surface" aria-labelledby="staging-title">
        <div class="col-head">
          <h2 id="staging-title">① 画面与章节编排</h2>
          <div class="mode-pills">
            <button
              class="mode-pill"
              :class="{ 'is-active': mode === 'upload' }"
              type="button"
              @click="mode = 'upload'"
            >
              网页多图上传
            </button>
            <button
              class="mode-pill"
              :class="{ 'is-active': mode === 'path' }"
              type="button"
              @click="mode = 'path'"
            >
              服务器目录导入
            </button>
          </div>
        </div>

        <div v-if="mode === 'upload'" class="upload-flow">
          <label class="multi-toggle">
            <input v-model="isMulti" type="checkbox" />
            <span>开启多章节（分话合集）</span>
          </label>

          <!-- Multi-chapter tabs -->
          <div v-if="isMulti" class="chapter-tabs-bar">
            <div class="chapter-tabs">
              <div
                v-for="(ch, idx) in chapters"
                :key="ch.id"
                class="chapter-tab"
                :class="{ 'is-active': activeChapterIdx === idx }"
                @click="activeChapterIdx = idx"
              >
                <input v-model="ch.title" class="chap-title-input" type="text" @click.stop />
                <span class="chap-badge">{{ ch.files.length }}P</span>
                <button
                  v-if="chapters.length > 1"
                  class="chap-del-btn"
                  type="button"
                  title="删除本话"
                  @click.stop="removeChapter(idx)"
                >
                  ×
                </button>
              </div>
            </div>
            <button class="btn btn-ghost add-chap-btn" type="button" @click="addChapter">
              ＋ 新增话
            </button>
          </div>

          <!-- Dropzone -->
          <div
            ref="dropAreaRef"
            class="drop-area"
            :class="{ 'is-dragover': isOverDropZone }"
            @click="() => openFileDialog()"
          >
            <div class="drop-content">
              <svg
                viewBox="0 0 24 24"
                width="36"
                height="36"
                stroke="currentColor"
                stroke-width="1.6"
                fill="none"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <p class="drop-lead">
                {{
                  isMulti
                    ? `点击或拖入图片至【${chapters[activeChapterIdx]?.title}】`
                    : '点击或批量拖入图片至此'
                }}
              </p>
              <span class="drop-sub">支持 JPG, PNG, WebP, GIF, AVIF（自动按文件名自然排序）</span>
            </div>
          </div>

          <!-- File summary -->
          <div class="staged-summary">
            <span>
              已暂存：<strong>{{ totalStagedFilesCount }}</strong> 张画面
              <template v-if="isMulti">（共 {{ chapters.length }} 话）</template>
            </span>
            <button
              v-if="totalStagedFilesCount > 0"
              class="btn btn-ghost btn-sm"
              type="button"
              @click="clearCurrentStaged"
            >
              清空当前
            </button>
          </div>

          <!-- Upload Progress -->
          <div v-if="isUploading" class="upload-progress-card">
            <div class="progress-info">
              <span>正在分批推送到书库（3 路并发）…</span>
              <span>{{ completedCount }} / {{ totalCount }} 页（{{ progress }}%）</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: `${progress}%` }" />
            </div>
          </div>
        </div>

        <div v-else class="path-flow">
          <div class="field-group">
            <label class="form-label" for="local-path">服务器本地目录路径 *</label>
            <input
              id="local-path"
              v-model="serverPath"
              class="field-input"
              type="text"
              placeholder="如：public/tiya-frames 或 /data/comics/tiya"
            />
          </div>
          <div class="path-guide">
            <h3>📖 目录识别规则：</h3>
            <ul>
              <li>
                <strong>单话图集</strong>：目录下直接平铺图片文件（如
                <code>tiya-frames/frame_0001.webp</code>），自动收录为单话。
              </li>
              <li>
                <strong>多话合集</strong>：目录下包含子文件夹（如 <code>01_第一话/</code>,
                <code>02_第二话/</code>），自动按子文件夹拆分为多章节。
              </li>
            </ul>
          </div>
        </div>
      </section>

      <!-- Right Column: Catalog Card Form -->
      <section class="form-col surface" aria-labelledby="form-title">
        <h2 id="form-title">② 典藏卡片与元数据</h2>

        <form class="meta-form" @submit.prevent="submit">
          <div class="field-group">
            <label class="form-label" for="meta-title">作品标题 (Title) *</label>
            <input
              id="meta-title"
              v-model="title"
              class="field-input field-input--lg"
              type="text"
              required
              placeholder="如：缇雅 (Tiya) 视频拆帧精选"
            />
          </div>

          <div class="grid-2">
            <div class="field-group">
              <label class="form-label" for="meta-slug">车号 Slug（选填，留空自动生成）</label>
              <div class="slug-field">
                <span class="slug-prefix">LOC_</span>
                <input
                  id="meta-slug"
                  v-model="slugId"
                  class="field-input"
                  type="text"
                  placeholder="tiya-frames"
                />
              </div>
            </div>

            <div class="field-group">
              <label class="form-label" for="meta-works">原作 / 企划 (Works)</label>
              <input
                id="meta-works"
                v-model="works"
                class="field-input"
                type="text"
                placeholder="如：原创"
              />
            </div>
          </div>

          <div class="grid-2">
            <div class="field-group">
              <label class="form-label" for="meta-authors">创作者 (Authors)</label>
              <input
                id="meta-authors"
                v-model="authors"
                class="field-input"
                type="text"
                placeholder="如：自制 / 拆帧组"
              />
            </div>

            <div class="field-group">
              <label class="form-label" for="meta-actors">登场人物 (Actors)</label>
              <input
                id="meta-actors"
                v-model="actors"
                class="field-input"
                type="text"
                placeholder="如：缇雅"
              />
            </div>
          </div>

          <div class="field-group">
            <label class="form-label" for="meta-uploader">上传 / 整理者 (Uploader)</label>
            <input
              id="meta-uploader"
              v-model="uploader"
              class="field-input"
              type="text"
              placeholder="如：馆长"
            />
          </div>

          <div class="field-group">
            <label class="form-label">封面展示页码 (Cover Pages · 轮播 4 张)</label>
            <CoverIndicesPicker v-model="coverIndices" :max-page="totalStagedFilesCount || 1" />
          </div>

          <div class="field-group">
            <label class="form-label">分类标签 (Tags)</label>
            <TagManager v-model="tags" />
          </div>

          <div class="field-group">
            <label class="form-label" for="meta-desc">作品叙述 (Description)</label>
            <textarea
              id="meta-desc"
              v-model="description"
              class="field-textarea"
              rows="3"
              placeholder="填写真实的作品背景、拆帧来源或阅读说明…"
            />
          </div>

          <div class="form-actions">
            <button class="btn btn-ghost" type="button" @click="goBack">取消</button>
            <button
              class="btn btn-primary btn-submit"
              type="submit"
              :disabled="
                submitting ||
                isUploading ||
                !title.trim() ||
                (mode === 'upload' && totalStagedFilesCount === 0) ||
                (mode === 'path' && !serverPath.trim())
              "
            >
              {{ submitting || isUploading ? '收录中…' : '确认创建并收录到纸间' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<style scoped>
.create-view {
  padding-block: var(--space-6) var(--space-10);
  display: grid;
  gap: var(--space-6);
}

.create-head {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
}

.create-head h1 {
  font-size: var(--text-xl);
}

.create-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: var(--space-5);
  align-items: start;
}

.staging-col,
.form-col {
  padding: var(--space-5);
  display: grid;
  gap: var(--space-4);
}

.col-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.staging-col h2,
.form-col h2 {
  font-size: var(--text-md);
  font-family: var(--font-display);
}

.mode-pills {
  display: inline-flex;
  gap: var(--space-1);
  background: var(--paper-1);
  padding: 0.25rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
}

.mode-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0.85rem;
  border: 0;
  border-radius: var(--radius-1);
  background: transparent;
  font-size: var(--text-xs);
  line-height: 1.2;
  color: var(--ink-1);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.mode-pill:hover:not(.is-active) {
  color: var(--ink-0);
}

.mode-pill.is-active {
  background: var(--paper-0);
  color: var(--accent-strong);
  box-shadow: var(--shadow-1);
  font-weight: 600;
}

.upload-flow {
  display: grid;
  gap: var(--space-3);
}

.multi-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--ink-1);
  cursor: pointer;
}

.multi-toggle input {
  accent-color: var(--accent);
}

.chapter-tabs-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  padding: var(--space-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 40%, transparent);
}

.chapter-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1-5);
}

.chapter-tab {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0.2rem 0.4rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  background: var(--paper-0);
  font-size: var(--text-xs);
  cursor: pointer;
}

.chapter-tab.is-active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.chap-title-input {
  border: 0;
  background: transparent;
  width: 5.5rem;
  font-size: var(--text-xs);
  color: var(--ink-0);
}

.chap-title-input:focus {
  outline: 1px solid var(--accent);
}

.chap-badge {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--ink-2);
}

.chap-del-btn {
  border: 0;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  font-size: 0.85rem;
}

.chap-del-btn:hover {
  color: var(--accent-strong);
}

.add-chap-btn {
  padding: 0.2rem 0.6rem;
  font-size: var(--text-xs);
}

.drop-area {
  padding: var(--space-8) var(--space-4);
  border: 2px dashed var(--line-strong);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 50%, transparent);
  text-align: center;
  cursor: pointer;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.drop-area:hover,
.drop-area.is-dragover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.drop-content {
  display: grid;
  place-items: center;
  gap: var(--space-2);
}

.drop-lead {
  font-size: var(--text-sm);
  color: var(--ink-0);
  font-weight: 500;
}

.drop-sub {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.staged-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-1);
  background: var(--paper-1);
  font-size: var(--text-xs);
}

.upload-progress-card {
  display: grid;
  gap: var(--space-1-5);
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.progress-track {
  height: 6px;
  border-radius: 999px;
  background: var(--paper-2);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  transition: width var(--duration-2) var(--ease-out);
}

.path-flow {
  display: grid;
  gap: var(--space-4);
}

.path-guide {
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  font-size: var(--text-xs);
  color: var(--ink-1);
  line-height: 1.6;
}

.path-guide h3 {
  font-size: var(--text-xs);
  margin-bottom: var(--space-1);
}

.path-guide ul {
  padding-left: var(--space-4);
  display: grid;
  gap: var(--space-1);
}

.path-guide code {
  font-family: var(--font-mono);
  color: var(--accent-strong);
}

.meta-form {
  display: grid;
  gap: var(--space-4);
}

.field-group {
  display: grid;
  gap: var(--space-1-5);
}

.form-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-1);
}

.field-input,
.field-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-0);
  font-size: var(--text-sm);
  font-family: inherit;
}

.field-input:focus,
.field-textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.field-input--lg {
  font-size: var(--text-md);
  font-family: var(--font-display);
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.slug-field {
  display: flex;
  align-items: center;
}

.slug-prefix {
  padding: var(--space-2) var(--space-2-5);
  border: 1px solid var(--line);
  border-right: 0;
  border-radius: var(--radius-2) 0 0 var(--radius-2);
  background: var(--paper-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent-strong);
}

.slug-field .field-input {
  border-radius: 0 var(--radius-2) var(--radius-2) 0;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.btn-submit {
  padding-inline: var(--space-5);
}

@media (max-width: 960px) {
  .create-grid {
    grid-template-columns: 1fr;
  }
}
</style>

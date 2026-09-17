<script setup lang="ts">
import { useLocalWorkshop } from '@/composables/useLocalWorkshop'
import { useHierarchicalNavigation } from '@/composables/useHierarchicalNavigation'
import TagManager from '@/components/form/TagManager.vue'
import CoverIndicesPicker from '@/components/form/CoverIndicesPicker.vue'
import SegmentedTabs from '@/components/SegmentedTabs.vue'
import FileStagingDropZone from '@/components/form/FileStagingDropZone.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppProgressBar from '@/components/AppProgressBar.vue'

const { goUpFromCreate } = useHierarchicalNavigation()

const {
  mode,
  modeTabs,
  isMulti,
  slugId,
  title,
  works,
  authors,
  actors,
  uploader,
  description,
  tags,
  serverPath,
  coverIndices,
  submitting,
  activeChapterIdx,
  chapters,
  currentChapterFiles,
  dropAreaRef,
  isOverDropZone,
  openFileDialog,
  addChapter,
  removeChapter,
  clearCurrentStaged,
  totalStagedFilesCount,
  isUploading,
  progress,
  completedCount,
  totalCount,
  submit,
  isInspectingPdf,
  stagedPdfMeta,
  inspectServerPdf,
  clearStagedPdf,
  chapterRanges,
} = useLocalWorkshop()
</script>

<template>
  <div class="create-view container">
    <header class="create-head surface">
      <AppButton
        class="back-btn"
        shape="circle"
        variant="ghost"
        size="md"
        icon="arrow-left"
        aria-label="返回书库"
        title="返回书库"
        @click="goUpFromCreate"
      />
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
          <SegmentedTabs v-model="mode" :items="modeTabs" size="sm" />
        </div>

        <!-- PDF Inspection Progress -->
        <div v-if="isInspectingPdf" class="pdf-inspect-card">
          <AppIcon name="book-open" size="md" />
          <div class="pdf-inspect-text">
            <strong>正在无损抽取并智能切分 PDF 章节...</strong>
            <span>基于双轨探测（PDF 电子大纲 + 本地轻量 OCR 扉页识别），预计数秒完成</span>
          </div>
        </div>

        <!-- PDF Staged Banner -->
        <div v-else-if="stagedPdfMeta" class="pdf-staged-banner">
          <div class="pdf-staged-left">
            <span class="pdf-badge">PDF 就绪</span>
            <div class="pdf-staged-title">
              <strong>{{ stagedPdfMeta.title }}</strong>
              <span class="pdf-staged-meta">
                共 {{ stagedPdfMeta.total_pages }} 页 · 已智能切分 {{ chapters.length }} 话 （{{
                  stagedPdfMeta.detection_track === 'toc'
                    ? '电子书签'
                    : stagedPdfMeta.detection_track === 'ocr'
                      ? 'OCR扉页探测'
                      : '单卷平铺'
                }}）
              </span>
            </div>
          </div>
          <AppButton
            variant="ghost"
            size="xs"
            icon="close"
            title="清除重置 PDF 暂存"
            aria-label="清除重置 PDF 暂存"
            @click="clearStagedPdf"
          >
            重置
          </AppButton>
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
                <AppButton
                  v-if="chapters.length > 1"
                  class="chap-del-btn"
                  shape="circle"
                  variant="ghost"
                  size="xs"
                  icon="close"
                  title="删除本话"
                  aria-label="删除本话"
                  @click.stop="removeChapter(idx)"
                />
              </div>
            </div>
            <AppButton variant="ghost" size="xs" icon="plus" @click="addChapter">
              新增话
            </AppButton>
          </div>

          <!-- PDF Chapter Breakdown Panel (when PDF is staged) -->
          <div v-if="stagedPdfMeta" class="pdf-breakdown-card">
            <div class="pdf-breakdown-head">
              <AppIcon name="book-open" size="sm" />
              <h3>PDF 画卷切分清单（{{ chapters.length }} 话 · {{ totalStagedFilesCount }} 页）</h3>
            </div>
            <div class="pdf-breakdown-list">
              <div
                v-for="(ch, idx) in chapters"
                :key="ch.id"
                class="pdf-breakdown-item"
                :class="{ 'is-active': activeChapterIdx === idx }"
                @click="activeChapterIdx = idx"
              >
                <span class="pdf-item-idx">#{{ idx + 1 }}</span>
                <input
                  v-model="ch.title"
                  class="pdf-item-title-input"
                  type="text"
                  placeholder="章节标题"
                  @click.stop
                />
                <span class="pdf-item-range">
                  P{{ chapterRanges[idx]?.start }} ~ P{{ chapterRanges[idx]?.end }}
                  <small>({{ chapterRanges[idx]?.count }}P)</small>
                </span>
                <AppButton
                  v-if="chapters.length > 1"
                  class="pdf-item-del"
                  shape="circle"
                  variant="ghost"
                  size="xs"
                  icon="close"
                  title="合并至上一章节"
                  aria-label="合并至上一章节"
                  @click.stop="removeChapter(idx)"
                />
              </div>
            </div>
            <p class="pdf-breakdown-note">
              <AppIcon name="info" size="xs" />
              <span
                >画卷已在本地完成无损解包。如需调整，可直接修改各话标题或点击删除图标与相邻话次合并。</span
              >
            </p>
          </div>

          <!-- Staging Drop Zone (when NOT staged PDF) -->
          <div
            v-else
            :ref="
              (el) => {
                dropAreaRef = el as HTMLElement
              }
            "
          >
            <FileStagingDropZone
              v-model:mode="mode"
              v-model:files="currentChapterFiles"
              v-model:server-path="serverPath"
              :show-tabs="false"
              :is-over-drop-zone="isOverDropZone"
              :open-file-dialog="openFileDialog"
              :disabled="submitting"
              :prompt="
                isMulti
                  ? `点击或拖入图片至【${chapters[activeChapterIdx]?.title}】`
                  : '点击或批量拖入图片至此'
              "
              @clear="clearCurrentStaged"
            >
              <template #summary>
                <div class="staged-summary">
                  <span>
                    已暂存：<strong>{{ totalStagedFilesCount }}</strong> 张画面
                    <template v-if="isMulti">（共 {{ chapters.length }} 话）</template>
                  </span>
                  <AppButton
                    v-if="totalStagedFilesCount > 0"
                    variant="ghost"
                    size="sm"
                    type="button"
                    @click="clearCurrentStaged"
                  >
                    清空当前
                  </AppButton>
                </div>
              </template>
            </FileStagingDropZone>
          </div>

          <!-- Upload Progress -->
          <div v-if="isUploading" class="upload-progress-card">
            <div class="progress-info">
              <span>正在分批推送到书库（3 路并发）…</span>
              <span>{{ completedCount }} / {{ totalCount }} 页（{{ progress }}%）</span>
            </div>
            <AppProgressBar
              :value="progress"
              :max="100"
              variant="track"
              color="accent"
              animated
              label="画页推送进度"
            />
          </div>
        </div>

        <div v-else class="path-flow">
          <div v-if="serverPath.trim().toLowerCase().endsWith('.pdf')" class="server-pdf-bar">
            <AppButton
              variant="secondary"
              size="sm"
              icon="book-open"
              :loading="isInspectingPdf"
              @click="inspectServerPdf"
            >
              预先分析并切分 PDF 章节
            </AppButton>
          </div>

          <FileStagingDropZone
            v-model:mode="mode"
            v-model:server-path="serverPath"
            :show-tabs="false"
            :disabled="submitting"
            path-label="服务器本地路径（目录或单文件 PDF）*"
            path-placeholder="如：/storage/comics/manga.pdf 或 /app/data/comics/vol1"
          >
            <template #path-guide>
              <div class="path-guide">
                <h3>
                  <AppIcon name="book-open" size="xs" />
                  <span>路径识别与分话规则：</span>
                </h3>
                <ul>
                  <li>
                    <strong>单文件/合订 PDF</strong>：直接输入 <code>.pdf</code> 路径（如
                    <code>/storage/comics/与你相恋到生命尽头第1卷.pdf</code
                    >），系统将自动无损抽取画卷并智能切分章节。
                  </li>
                  <li>
                    <strong>单话图集</strong>：目录下直接平铺图片文件（如
                    <code>tiya-frames/frame_0001.webp</code>），自动收录为单话。
                  </li>
                  <li>
                    <strong>多话合集</strong>：目录下包含子文件夹或多个
                    <code>.pdf</code> 文件，自动拆分为多章节。
                  </li>
                </ul>
              </div>
            </template>
          </FileStagingDropZone>
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
              placeholder="如：lhvision"
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
            <AppButton variant="ghost" size="lg" type="button" @click="goUpFromCreate">
              取消
            </AppButton>
            <AppButton
              variant="primary"
              size="lg"
              type="submit"
              class="btn-submit"
              :loading="submitting || isUploading"
              :disabled="
                !title.trim() ||
                (mode === 'upload' && totalStagedFilesCount === 0) ||
                (mode === 'path' && !serverPath.trim())
              "
            >
              {{ submitting || isUploading ? '收录中…' : '确认创建并收录到纸间' }}
            </AppButton>
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
  padding: var(--space-badge-y) var(--space-1);
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

.pdf-inspect-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--accent);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  color: var(--accent-strong);
}

.pdf-inspect-text {
  display: grid;
  gap: var(--space-0-5);
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.pdf-inspect-text strong {
  color: var(--ink-0);
  font-size: var(--text-sm);
}

.pdf-staged-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-1);
}

.pdf-staged-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.pdf-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-1);
  background: var(--accent);
  color: #fff;
  font-size: var(--text-2xs);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.pdf-staged-title {
  display: grid;
  gap: var(--space-0-5);
}

.pdf-staged-title strong {
  font-size: var(--text-sm);
  color: var(--ink-0);
}

.pdf-staged-meta {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.pdf-breakdown-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-1);
}

.pdf-breakdown-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--ink-0);
}

.pdf-breakdown-head h3 {
  font-size: var(--text-sm);
  font-family: var(--font-display);
}

.pdf-breakdown-list {
  display: grid;
  gap: var(--space-1-5);
  max-height: 280px;
  overflow-y: auto;
  padding-right: var(--space-1);
}

.pdf-breakdown-item {
  display: flex;
  align-items: center;
  gap: var(--space-2-5);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out);
}

.pdf-breakdown-item:hover {
  border-color: var(--accent);
}

.pdf-breakdown-item.is-active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.pdf-item-idx {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  min-width: 24px;
}

.pdf-item-title-input {
  flex: 1;
  min-width: 0;
  padding: var(--space-1) var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-1);
  background: transparent;
  color: var(--ink-0);
  font-size: var(--text-xs);
  transition: all var(--duration-fast) var(--ease-out);
}

.pdf-item-title-input:focus {
  outline: none;
  background: var(--paper-1);
  border-color: var(--accent);
}

.pdf-item-range {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-1);
  white-space: nowrap;
}

.pdf-item-range small {
  color: var(--ink-2);
  margin-left: var(--space-1);
}

.pdf-breakdown-note {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1-5);
  font-size: var(--text-xs);
  color: var(--ink-2);
  line-height: 1.5;
  margin-top: var(--space-1);
}

.server-pdf-bar {
  display: flex;
  justify-content: flex-start;
  margin-bottom: var(--space-2);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--ink-1);
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
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
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

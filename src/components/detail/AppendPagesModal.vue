<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useFileDialog, useDropZone } from '@vueuse/core'
import Modal from '@/components/Modal.vue'
import SegmentedTabs from '@/components/SegmentedTabs.vue'
import AppButton from '@/components/AppButton.vue'
import { useUploadQueue } from '@/composables/useUploadQueue'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { ComicMeta } from '@/types'

const props = defineProps<{
  open: boolean
  meta: ComicMeta
}>()

const emit = defineEmits<{
  cancel: []
  appended: []
}>()

const { toast } = useToast()
const { isUploading, progress, completedCount, totalCount, uploadFiles } = useUploadQueue()

const mode = ref<'upload' | 'path'>('upload')
const modeTabs = [
  { key: 'upload' as const, label: '网页多图上传' },
  { key: 'path' as const, label: '服务器本地路径扫描' },
]
const appendType = ref<'current' | 'new'>('current')
const selectedChapterId = ref('')
const newChapterTitle = ref('')
const serverPath = ref('')
const selectedFiles = ref<File[]>([])
const submitting = ref(false)

const dropZoneRef = ref<HTMLElement | null>(null)

function naturalSortFiles(files: File[]): File[] {
  return [...files].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }),
  )
}

function stageFiles(rawList: File[]) {
  const list = rawList.filter((f) => /\.(jpe?g|png|webp|gif|avif|bmp)$/i.test(f.name))
  selectedFiles.value = naturalSortFiles([...selectedFiles.value, ...list])
}

const { open: openFileDialog, onChange: onFileDialogChange } = useFileDialog({
  multiple: true,
  accept: 'image/*',
  reset: true,
})

onFileDialogChange((files) => {
  if (files) stageFiles(Array.from(files))
})

const { isOverDropZone } = useDropZone(dropZoneRef, {
  onDrop: (files) => {
    if (files) stageFiles(files)
  },
})

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      appendType.value = 'current'
      selectedChapterId.value = props.meta.chapters?.[0]?.id || ''
      newChapterTitle.value = props.meta.chapters?.length
        ? `第 ${props.meta.chapters.length + 1} 话`
        : '第 2 话'
      serverPath.value = ''
      selectedFiles.value = []
    }
  },
  { immediate: true },
)

const isMulti = computed(() => (props.meta.chapters?.length ?? 0) > 1)

const selectedChapter = computed(
  () => props.meta.chapters?.find((ch) => ch.id === selectedChapterId.value) ?? null,
)
const selectedChapterLabel = computed(() =>
  selectedChapter.value
    ? `第 ${selectedChapter.value.index} 话：${selectedChapter.value.title}（当前 ${selectedChapter.value.page_count} 页）`
    : '',
)

async function submit() {
  submitting.value = true
  try {
    const targetChap = appendType.value === 'new' ? '' : selectedChapterId.value
    const newTitle = appendType.value === 'new' ? newChapterTitle.value.trim() : ''

    if (mode.value === 'upload') {
      if (selectedFiles.value.length === 0) {
        toast('请先选择要上传的图片文件', 'error')
        submitting.value = false
        return
      }

      await uploadFiles(props.meta.source_id, selectedFiles.value, targetChap, newTitle)
      toast(`已成功追加 ${selectedFiles.value.length} 页`, 'info')
      emit('appended')
    } else {
      if (!serverPath.value.trim()) {
        toast('请输入服务器本地目录路径', 'error')
        submitting.value = false
        return
      }

      await api.appendLocalComic(props.meta.source_id, {
        server_path: serverPath.value.trim(),
        target_chapter: targetChap,
        new_chapter_title: newTitle,
      })
      toast('已成功从本地目录增量追加页面', 'info')
      emit('appended')
    }
  } catch (err) {
    toast(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Modal :open="open" title="增量追加页面 / 章节" @cancel="emit('cancel')">
    <div class="append-modal-body">
      <div class="append-type-group">
        <label class="form-label">追加目标位置</label>
        <div class="radio-cards">
          <label class="radio-card" :class="{ 'is-active': appendType === 'current' }">
            <input v-model="appendType" type="radio" value="current" />
            <div>
              <strong>追加至已有章节 / 末尾</strong>
              <p class="radio-desc">
                {{
                  isMulti
                    ? '追加到指定的已有话末尾'
                    : `当前已有 ${meta.page_count} 页，新页面从第 ${meta.page_count + 1} 页起顺延`
                }}
              </p>
            </div>
          </label>

          <label class="radio-card" :class="{ 'is-active': appendType === 'new' }">
            <input v-model="appendType" type="radio" value="new" />
            <div>
              <strong>创建并追加为新一话</strong>
              <p class="radio-desc">
                将这批图片作为《{{ meta.title }}》的新章节（第
                {{ (meta.chapters?.length || 1) + 1 }} 话）
              </p>
            </div>
          </label>
        </div>
      </div>

      <div v-if="appendType === 'current' && isMulti">
        <label class="form-label" for="select-chap">选择目标章节</label>
        <select
          id="select-chap"
          v-model="selectedChapterId"
          class="field-select"
          :title="selectedChapterLabel"
        >
          <option
            v-for="ch in meta.chapters"
            :key="ch.id"
            :value="ch.id"
            :title="`第 ${ch.index} 话：${ch.title}（当前 ${ch.page_count} 页）`"
          >
            第 {{ ch.index }} 话：{{ ch.title }}（当前 {{ ch.page_count }} 页）
          </option>
        </select>
      </div>

      <div v-if="appendType === 'new'">
        <label class="form-label" for="new-chap-title">新章节标题</label>
        <input
          id="new-chap-title"
          v-model="newChapterTitle"
          class="field-input"
          type="text"
          placeholder="如：第 2 话 / 最终回"
        />
      </div>

      <div>
        <SegmentedTabs v-model="mode" :items="modeTabs" size="sm" />
      </div>

      <div v-if="mode === 'upload'" class="upload-zone">
        <div
          ref="dropZoneRef"
          class="upload-zone__inner"
          :class="{ 'is-dragover': isOverDropZone }"
          @click="() => openFileDialog()"
        >
          <svg
            viewBox="0 0 24 24"
            width="28"
            height="28"
            stroke="currentColor"
            stroke-width="1.8"
            fill="none"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <p>点击选择图片，或将图片批量拖拽到此处</p>
          <span class="upload-hint">支持 JPG, PNG, WebP, GIF, AVIF</span>
        </div>

        <div v-if="selectedFiles.length > 0" class="file-summary">
          <span
            >已选择 <strong>{{ selectedFiles.length }}</strong> 张图片</span
          >
          <button class="btn btn-ghost btn-xs" type="button" @click="selectedFiles = []">
            清空
          </button>
        </div>
      </div>

      <div v-else class="path-zone">
        <label class="form-label" for="append-path">服务器目录相对/绝对路径</label>
        <input
          id="append-path"
          v-model="serverPath"
          class="field-input"
          type="text"
          placeholder="如：public/tiya-frames 或 /data/manga/vol2"
        />
        <p class="path-hint">指定包含图片的文件夹，系统将就地扫描并按文件名自然序号追加。</p>
      </div>

      <div v-if="isUploading" class="upload-progress-card">
        <div class="progress-info">
          <span>正在推送到书库（3 路并发）…</span>
          <span>{{ completedCount }} / {{ totalCount }} 页（{{ progress }}%）</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: `${progress}%` }" />
        </div>
      </div>
    </div>

    <template #footer>
      <AppButton
        variant="ghost"
        size="md"
        :disabled="submitting || isUploading"
        @click="emit('cancel')"
      >
        取消
      </AppButton>
      <AppButton
        variant="primary"
        size="md"
        :loading="submitting || isUploading"
        :disabled="
          (mode === 'upload' && selectedFiles.length === 0) ||
          (mode === 'path' && !serverPath.trim())
        "
        @click="submit"
      >
        {{ submitting || isUploading ? '正在追加…' : '确认追加' }}
      </AppButton>
    </template>
  </Modal>
</template>

<style scoped>
.append-modal-body {
  display: grid;
  gap: var(--space-4);
}

.append-type-group {
  display: grid;
  gap: var(--space-2);
}

.form-label {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-1);
}

.radio-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.radio-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2-5);
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.radio-card:hover {
  border-color: var(--accent);
}

.radio-card.is-active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.radio-card input {
  margin-top: 0.2rem;
  accent-color: var(--accent);
}

.radio-card strong {
  display: block;
  font-size: var(--text-xs);
  color: var(--ink-0);
}

.radio-desc {
  margin-top: 0.2rem;
  font-size: var(--text-xs);
  color: var(--ink-2);
  line-height: 1.4;
}

.upload-zone {
  display: grid;
  gap: var(--space-2);
}

.upload-zone__inner {
  display: grid;
  place-items: center;
  gap: var(--space-2);
  padding: var(--space-6) var(--space-4);
  border: 2px dashed var(--line-strong);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 50%, transparent);
  color: var(--ink-1);
  text-align: center;
  cursor: pointer;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.upload-zone__inner:hover,
.upload-zone__inner.is-dragover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.upload-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.file-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-1);
  background: var(--paper-1);
  font-size: var(--text-xs);
}

.path-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
  line-height: 1.5;
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
}

@media (max-width: 640px) {
  .radio-cards {
    grid-template-columns: 1fr;
  }
}
</style>

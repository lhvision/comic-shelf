<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import FileStagingDropZone from '@/components/form/FileStagingDropZone.vue'
import { api } from '@/api/client'
import { useFileStaging } from '@/composables/useFileStaging'
import { useToast } from '@/composables/useToast'
import { useSystemEvents } from '@/composables/useSystemEvents'
import type { ComicMeta } from '@/types'

const props = defineProps<{
  open: boolean
  meta: ComicMeta
}>()

const emit = defineEmits<{
  cancel: []
  replaced: []
}>()

const { toast } = useToast()
const { broadcastLocalChange } = useSystemEvents()

const mode = ref<'upload' | 'path'>('upload')

const replaceScope = ref<'full' | 'chapter'>('full')
const selectedChapterId = ref('')
const serverPath = ref('')
const submitting = ref(false)
const ackReplace = ref(false)
const uploadAbortController = ref<AbortController | null>(null)

const {
  files: selectedFiles,
  dropZoneRef,
  isOverDropZone,
  openFileDialog,
} = useFileStaging({ deduplicate: true, notifyIgnored: true, disabled: submitting })

function cancelModal() {
  if (uploadAbortController.value) {
    uploadAbortController.value.abort()
    uploadAbortController.value = null
  }
  submitting.value = false
  emit('cancel')
}

onBeforeUnmount(() => {
  if (uploadAbortController.value) {
    uploadAbortController.value.abort()
    uploadAbortController.value = null
  }
})

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      if (uploadAbortController.value) {
        uploadAbortController.value.abort()
        uploadAbortController.value = null
      }
      mode.value = 'upload'
      replaceScope.value =
        props.meta.chapters && props.meta.chapters.length > 1 ? 'chapter' : 'full'
      selectedChapterId.value = props.meta.chapters?.[0]?.id || ''
      serverPath.value = ''
      selectedFiles.value = []
      ackReplace.value = false
      submitting.value = false
    }
  },
  { immediate: true },
)

const isMulti = computed(() => (props.meta.chapters?.length ?? 0) > 1)

const targetDescription = computed(() => {
  if (isMulti.value && replaceScope.value === 'chapter') {
    const ch = props.meta.chapters?.find((c) => c.id === selectedChapterId.value)
    return ch ? `第 ${ch.index} 话《${ch.title}》（现有 ${ch.page_count} 页）` : '选定章节'
  }
  return `整本《${props.meta.title}》（现有 ${props.meta.page_count} 页）`
})

const existingPageCount = computed(() => {
  if (isMulti.value && replaceScope.value === 'chapter') {
    const ch = props.meta.chapters?.find((c) => c.id === selectedChapterId.value)
    return ch?.page_count ?? 0
  }
  return props.meta.page_count ?? 0
})

const pageDelta = computed(() => {
  if (selectedFiles.value.length === 0) return 0
  return selectedFiles.value.length - existingPageCount.value
})

const deltaLabel = computed(() => {
  if (selectedFiles.value.length === 0) return ''
  if (pageDelta.value > 0) return `+${pageDelta.value} 页`
  if (pageDelta.value < 0) return `${pageDelta.value} 页`
  return '页数持平'
})

function onDropzoneTrigger() {
  if (!submitting.value) {
    openFileDialog()
  }
}

async function submit() {
  if (mode.value === 'upload') {
    if (selectedFiles.value.length === 0) {
      toast('请先选择要替换的图片文件', 'error')
      return
    }
  } else {
    if (!serverPath.value.trim()) {
      toast('请输入服务器本地目录或图片路径', 'error')
      return
    }
  }

  if (!ackReplace.value) {
    toast('请先勾选确认了解覆盖后果', 'error')
    return
  }

  submitting.value = true
  const controller = new AbortController()
  uploadAbortController.value = controller

  try {
    const targetChap =
      isMulti.value && replaceScope.value === 'chapter' ? selectedChapterId.value : ''

    if (mode.value === 'upload') {
      await api.replaceComicPages(
        props.meta.source,
        props.meta.source_id,
        selectedFiles.value,
        targetChap,
        { signal: controller.signal },
      )
      toast(`已成功重新装订 ${selectedFiles.value.length} 页新画页，并开启保护`, 'success')
    } else {
      await api.replaceComicPagesFromPath(
        props.meta.source,
        props.meta.source_id,
        serverPath.value.trim(),
        targetChap,
        { signal: controller.signal },
      )
      toast('已成功从服务器本地路径扫描并完成重新装订，已开启保护', 'success')
    }
    broadcastLocalChange({
      action: 'update_pages',
      source: props.meta.source,
      source_id: props.meta.source_id,
      timestamp: Date.now(),
    })
    emit('replaced')
  } catch (err) {
    if (controller.signal.aborted) return
    toast(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    if (uploadAbortController.value === controller) {
      uploadAbortController.value = null
      submitting.value = false
    }
  }
}
</script>

<template>
  <Modal :open="open" title="重新装订画页" @cancel="cancelModal">
    <div class="replace-modal-body" :class="{ 'is-submitting': submitting }">
      <div class="replace-alert" role="alert">
        <AppIcon name="archive" size="18" class="replace-alert-icon" />
        <div class="replace-alert-text">
          <strong>重订操作提示</strong>
          <p>
            上传或扫描成功后将用新画页彻底替换
            <span>{{ targetDescription }}</span> 的现有内容，旧画页将被完全清除且不可撤销。
            <template v-if="meta.source !== 'local'">
              重新装订后将自动启用<strong>重订保护</strong>标记，防止远端同步冲掉手动装订的画页。
            </template>
          </p>
        </div>
      </div>

      <div v-if="isMulti" class="scope-group">
        <label class="form-label">装订范围</label>
        <div class="radio-cards">
          <label
            class="radio-card"
            :class="{ 'is-active': replaceScope === 'chapter', 'is-disabled': submitting }"
          >
            <input v-model="replaceScope" type="radio" value="chapter" :disabled="submitting" />
            <div>
              <strong>仅重订指定章节</strong>
              <p class="radio-desc">只更新选定话的画页，保留其余章节及目录划分</p>
            </div>
          </label>

          <label
            class="radio-card"
            :class="{ 'is-active': replaceScope === 'full', 'is-disabled': submitting }"
          >
            <input v-model="replaceScope" type="radio" value="full" :disabled="submitting" />
            <div>
              <strong>整部重新装订</strong>
              <p class="radio-desc">将整部作品所有画页重新装订为这批图片（抹除多话合并为单卷）</p>
            </div>
          </label>
        </div>

        <div v-if="replaceScope === 'full'" class="scope-danger-warn">
          <AppIcon name="info" size="14" />
          <span>注意：整部重新装订将彻底销毁现有多章节划分，不可逆转。</span>
        </div>
      </div>

      <div v-if="isMulti && replaceScope === 'chapter'" class="field-group">
        <label class="form-label" for="replace-select-chap">选择要重订的目标章节</label>
        <select
          id="replace-select-chap"
          v-model="selectedChapterId"
          class="field-select"
          :disabled="submitting"
        >
          <option v-for="ch in meta.chapters" :key="ch.id" :value="ch.id">
            第 {{ ch.index }} 话：{{ ch.title }}（现有 {{ ch.page_count }} 页）
          </option>
        </select>
      </div>

      <div ref="dropZoneRef">
        <div v-if="mode === 'upload'" class="field-header">
          <label class="form-label">装入新画页图片（纯图片，按文件名排序）</label>
          <div v-if="selectedFiles.length" class="page-diff-badge">
            <span>现有 {{ existingPageCount }} 页</span>
            <AppIcon name="arrow-right" size="xs" />
            <span>新装订 {{ selectedFiles.length }} 页</span>
            <span class="page-delta">({{ deltaLabel }})</span>
          </div>
        </div>

        <FileStagingDropZone
          v-model:mode="mode"
          v-model:files="selectedFiles"
          v-model:server-path="serverPath"
          :is-over-drop-zone="isOverDropZone"
          :open-file-dialog="onDropzoneTrigger"
          :disabled="submitting"
          path-placeholder="如：public/tiya-frames 或 /data/comics/import-folder"
        >
          <template #path-guide>
            <p class="path-hint">
              指定服务器上包含画页的文件夹或图片路径，系统将就地扫描并按文件名自然序号重新装订。
            </p>
          </template>
        </FileStagingDropZone>
      </div>

      <label class="replace-ack" :class="{ 'is-disabled': submitting }">
        <input v-model="ackReplace" type="checkbox" :disabled="submitting" />
        <span>我已了解：将完全清除原有画页并重新装订，不可撤销。</span>
      </label>
    </div>

    <template #footer>
      <AppButton variant="ghost" size="md" type="button" @click="cancelModal"> 取消 </AppButton>
      <AppButton
        :variant="isMulti && replaceScope === 'full' ? 'danger' : 'primary'"
        size="md"
        type="button"
        :loading="submitting"
        :disabled="
          (mode === 'upload' && selectedFiles.length === 0) ||
          (mode === 'path' && !serverPath.trim()) ||
          !ackReplace ||
          submitting
        "
        @click="submit"
      >
        {{ isMulti && replaceScope === 'full' ? '确认整部重订' : '确认重新装订' }}
        <template v-if="mode === 'upload' && selectedFiles.length">
          （{{ selectedFiles.length }} 页）
        </template>
      </AppButton>
    </template>
  </Modal>
</template>

<style scoped>
.replace-modal-body {
  display: grid;
  gap: var(--space-4);
  transition: opacity var(--duration-1) var(--ease-out);
}

.replace-modal-body.is-submitting {
  pointer-events: none;
  opacity: 0.7;
}

.replace-alert {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  font-size: var(--text-sm);
  line-height: 1.5;
}

.replace-alert-icon {
  flex-shrink: 0;
  color: var(--accent);
  margin-top: 2px;
}

.replace-alert-text strong {
  display: block;
  margin-bottom: 2px;
  color: var(--ink-0);
}

.replace-alert-text p {
  margin: 0;
  color: var(--ink-1);
}

.replace-alert-text p span {
  color: var(--ink-0);
  font-weight: 500;
}

.field-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.page-diff-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.page-delta {
  font-weight: 600;
  color: var(--accent);
  margin-left: var(--space-1);
}

.field-select,
.field-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  color: var(--ink-0);
  font-size: var(--text-sm);
  outline: none;
  transition: border-color var(--duration-1) var(--ease-out);
}

.field-select:focus,
.field-input:focus {
  border-color: var(--accent);
  outline: 2px solid var(--accent);
  outline-offset: 1px;
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

.radio-card:hover:not(.is-disabled) {
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

.scope-danger-warn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: color-mix(in oklab, var(--danger) 10%, var(--paper-1));
  border: 1px solid color-mix(in oklab, var(--danger) 25%, transparent);
  border-radius: var(--radius-1);
  color: var(--danger);
  font-size: var(--text-xs);
}

.path-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
  line-height: 1.5;
  margin: 0;
}

.replace-ack {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2.75rem;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-1);
  font-size: var(--text-sm);
  color: var(--ink-0);
  cursor: pointer;
  user-select: none;
}

.replace-ack input {
  accent-color: var(--accent);
}

.is-disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 640px) {
  .radio-cards {
    grid-template-columns: 1fr;
  }
}
</style>

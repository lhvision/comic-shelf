<script setup lang="ts">
/**
 * @file FileStagingDropZone.vue
 * @description 画卷文件暂存区与本地路径扫描双模输入组件。
 *
 * 领域概念（CONTEXT.md）：
 * 画卷文件暂存区（Staged File Rack / File Staging Drop Zone）
 * 统一收敛追加页面、重新装订与自建工坊中的图片拖拽暂存、多图选单与服务器路径输入。
 */

import { computed } from 'vue'
import SegmentedTabs, { type TabItem } from '@/components/SegmentedTabs.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const modeModel = defineModel<'upload' | 'path'>('mode', { default: 'upload' })
const filesModel = defineModel<File[]>('files', { default: () => [] })
const serverPathModel = defineModel<string>('serverPath', { default: '' })

const props = withDefaults(
  defineProps<{
    /** 是否处于提交/上传禁用状态 */
    disabled?: boolean
    /** 是否正处于文件拖拽悬停中 */
    isOverDropZone?: boolean
    /** 打开文件选择对话框回调 */
    openFileDialog?: () => void
    /** 拖拽区主文案 */
    prompt?: string
    /** 格式提示文案 */
    hint?: string
    /** 本地路径输入框占位符 */
    pathPlaceholder?: string
    /** 本地路径输入框标签 */
    pathLabel?: string
    /** 是否展示双模切换 Tab */
    showTabs?: boolean
  }>(),
  {
    disabled: false,
    isOverDropZone: false,
    openFileDialog: undefined,
    prompt: '点击选择画页，或将图片批量拖拽到此处',
    hint: '支持 JPG, PNG, WebP, GIF, AVIF（自动按文件名自然排序）',
    pathPlaceholder: '如：public/tiya-frames 或 /data/comics/tiya',
    pathLabel: '服务器本地目录绝对/相对路径',
    showTabs: true,
  },
)

const emit = defineEmits<{
  clear: []
}>()

const modeTabs: TabItem<'upload' | 'path'>[] = [
  { key: 'upload', label: '网页多图上传' },
  { key: 'path', label: '服务器本地路径扫描' },
]

const stagedSummary = computed(() => {
  const count = filesModel.value.length
  if (count === 0) return ''
  const first = filesModel.value[0]?.name || ''
  const last = filesModel.value[count - 1]?.name || ''
  return `已就绪 ${count} 张画页（首尾：${first} ~ ${last}）`
})

function onDropZoneClick() {
  if (props.disabled) return
  props.openFileDialog?.()
}

function handleClear() {
  filesModel.value = []
  emit('clear')
}
</script>

<template>
  <div class="file-staging-drop-zone">
    <div v-if="showTabs" class="mode-tabs-wrapper">
      <SegmentedTabs v-model="modeModel" :items="modeTabs" size="sm" />
    </div>

    <!-- 模式一：网页多图上传 -->
    <div v-if="modeModel === 'upload'" class="upload-zone-flow">
      <div
        class="drop-zone"
        role="button"
        tabindex="0"
        aria-label="点击选择画页，或将图片批量拖拽到此处"
        :aria-dropeffect="isOverDropZone ? 'copy' : 'none'"
        :class="{ 'is-dragover': isOverDropZone, 'is-disabled': disabled }"
        @click="onDropZoneClick"
        @keydown.enter.prevent="onDropZoneClick"
        @keydown.space.prevent="onDropZoneClick"
      >
        <AppIcon name="upload" size="2xl" />
        <p class="drop-prompt">{{ prompt }}</p>
        <span class="drop-hint">{{ hint }}</span>
      </div>

      <slot name="summary" :files="filesModel" :clear="handleClear">
        <div v-if="filesModel.length > 0" class="file-summary">
          <span class="staged-names" :title="stagedSummary">
            已就绪 <strong>{{ filesModel.length }}</strong> 张画页（首尾：{{
              filesModel[0]?.name
            }}
            ~ {{ filesModel[filesModel.length - 1]?.name }}）
          </span>
          <AppButton
            variant="ghost"
            size="xs"
            type="button"
            :disabled="disabled"
            @click.stop="handleClear"
          >
            清空
          </AppButton>
        </div>
      </slot>
    </div>

    <!-- 模式二：服务器本地路径扫描 -->
    <div v-else class="path-zone-flow">
      <div class="field-group">
        <label class="form-label" for="staging-server-path">{{ pathLabel }}</label>
        <input
          id="staging-server-path"
          v-model="serverPathModel"
          class="field-input"
          type="text"
          :placeholder="pathPlaceholder"
          :disabled="disabled"
        />
      </div>
      <slot name="path-guide" />
    </div>
  </div>
</template>

<style scoped>
.file-staging-drop-zone {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.mode-tabs-wrapper {
  margin-bottom: var(--space-1);
}

.upload-zone-flow {
  display: flex;
  flex-direction: column;
  gap: var(--space-2-5);
}

.drop-prompt {
  font-size: var(--text-sm);
  color: var(--ink-0);
  font-weight: 500;
  margin: 0;
}

.drop-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.drop-zone.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
  pointer-events: none;
}

.file-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
}

.staged-names {
  font-size: var(--text-xs);
  color: var(--ink-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.staged-names strong {
  color: var(--accent-strong);
  font-weight: 600;
}

.path-zone-flow {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>

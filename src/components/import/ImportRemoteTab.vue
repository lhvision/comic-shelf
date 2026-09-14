<script setup lang="ts">
/**
 * @file ImportRemoteTab.vue
 * @description 纸间远端数据源（禁漫、哔咔等）通用收录表单选项卡组件。
 *
 * 核心功能：
 * - 统一的车号/链接输入框与前缀标识徽标；
 * - 竖排文字提交按钮（支持导入中文字切分动画与禁用态）；
 * - 预取全书画页（`prefetchAll`）复选框与针对性提示说明；
 * - 集中收敛全站远端导入表单的响应式网格与动效样式，杜绝机械代码复制。
 */

import { computed, useTemplateRef } from 'vue'
import AppTooltip from '@/components/AppTooltip.vue'
import AppIcon from '@/components/AppIcon.vue'

/** 绑定的车号/链接输入值（v-model:id） */
const idModel = defineModel<string>('id', { default: '' })
/** 绑定的全量缓存选项（v-model:prefetchAll） */
const prefetchAllModel = defineModel<boolean>('prefetchAll', { default: false })

const props = withDefaults(
  defineProps<{
    /** 输入框前缀标识（如 JM、PICA） */
    prefix: string
    /** 输入框占位提示文本 */
    placeholder: string
    /** 输入框无障碍 aria-label */
    ariaLabel?: string
    /** 软键盘输入模式 */
    inputmode?: 'none' | 'text' | 'decimal' | 'numeric' | 'tel' | 'search' | 'email' | 'url'
    /** 全量缓存说明 Tooltip ID */
    tooltipId: string
    /** 全量缓存说明 Tooltip 提示文本 */
    tooltipText: string
    /** 是否正在执行收录导入请求 */
    importing: boolean
    /** 当前输入是否合法可提交 */
    canSubmit: boolean
  }>(),
  {
    ariaLabel: '',
    inputmode: 'text',
  },
)

const emit = defineEmits<{
  /** 触发提交收录（携带按钮元素以便触发 View Transition 扩散动画） */
  submit: [btnEl: HTMLButtonElement | null]
}>()

const submitBtnRef = useTemplateRef<HTMLButtonElement>('submitBtnRef')

/** 竖排按钮文字 */
const btnText = computed(() => (props.importing ? '收录中…' : '收录到纸间'))

/** 处理表单提交 */
function handleSubmit() {
  emit('submit', submitBtnRef.value)
}
</script>

<template>
  <div class="remote-tab-controls">
    <form class="import-form" @submit.prevent="handleSubmit">
      <label class="field import-field">
        <span class="field-prefix">{{ prefix }}</span>
        <input
          v-model="idModel"
          type="text"
          :inputmode="inputmode"
          autocomplete="off"
          :placeholder="placeholder"
          :aria-label="ariaLabel || ($attrs['aria-label'] as string) || placeholder"
        />
      </label>
      <button
        ref="submitBtnRef"
        class="import-submit-btn"
        type="submit"
        :disabled="!canSubmit || importing"
        aria-label="收录到纸间"
      >
        <span class="vertical-text">
          <span v-for="(char, idx) in btnText" :key="idx">{{ char }}</span>
        </span>
      </button>
    </form>

    <div class="download-settings__row">
      <label class="cache-check">
        <input v-model="prefetchAllModel" type="checkbox" />
        <span>同时缓存全部页面</span>
      </label>
      <AppTooltip :id="tooltipId" :tip="tooltipText" side="top">
        <button class="tooltip-icon" type="button" aria-label="关于缓存全部页面">
          <AppIcon name="info" size="xs" />
        </button>
      </AppTooltip>
    </div>
  </div>
</template>

<style scoped>
.remote-tab-controls {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.import-form {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-3);
  align-items: stretch;
}

.import-field {
  min-height: 7.2rem;
  padding: var(--space-4) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-3);
  background: var(--paper-0);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  transition:
    border-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out);
}

.import-field:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.field-prefix {
  font-family: var(--font-mono);
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 0.12em;
}

.import-field input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: var(--text-md);
  color: var(--ink-0);
}

.import-submit-btn {
  width: 3.6rem;
  padding: var(--space-3) 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--radius-3);
  background: var(--accent);
  color: var(--accent-contrast);
  cursor: pointer;
  user-select: none;
  transition:
    transform var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out),
    opacity var(--duration-1) var(--ease-out);
}

.import-submit-btn:hover:not(:disabled) {
  background: var(--accent-strong);
  box-shadow: var(--shadow-2);
}

.import-submit-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.vertical-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-0-5);
  font-size: var(--text-sm);
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: 1.1;
}

.download-settings__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 1.8rem;
}

.cache-check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.cache-check input {
  accent-color: var(--accent);
  width: 14px;
  height: 14px;
}

.tooltip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  padding: var(--space-0-5);
  border-radius: var(--radius-1);
}

.tooltip-icon:hover {
  color: var(--accent);
}
</style>

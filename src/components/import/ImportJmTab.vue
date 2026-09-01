<script setup lang="ts">
/**
 * @file ImportJmTab.vue
 * @description 禁漫车号收录表单选项卡面板。
 *
 * 核心功能：
 * - 禁漫车号输入与格式前缀 `JM`；
 * - 竖排文字提交按钮（支持导入中文字切分动画与禁用态）；
 * - 预取全书画页（`prefetchAll`）复选框与提示说明。
 */

import { computed, useTemplateRef } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import AppIcon from '@/components/AppIcon.vue'

/** 绑定的车号输入值（v-model:id） */
const idModel = defineModel<string>('id', { default: '' })
/** 绑定的全量缓存选项（v-model:prefetchAll） */
const prefetchAllModel = defineModel<boolean>('prefetchAll', { default: false })

const props = defineProps<{
  /** 是否正在执行收录导入请求 */
  importing: boolean
  /** 当前车号格式是否合法可提交 */
  canSubmit: boolean
}>()

const emit = defineEmits<{
  /** 触发提交收录（携带按钮元素以便触发 View Transition 扩散动画） */
  submit: [btnEl: HTMLButtonElement | null]
}>()

const submitBtnRef = useTemplateRef<HTMLButtonElement>('submitBtnRef')

/** 竖排按钮文字 */
const jmBtnText = computed(() => (props.importing ? '收录中…' : '收录到纸间'))

/** 处理表单提交 */
function handleSubmit() {
  emit('submit', submitBtnRef.value)
}
</script>

<template>
  <div class="jm-tab-controls">
    <form class="import-form" @submit.prevent="handleSubmit">
      <label class="field import-field">
        <span class="field-prefix">JM</span>
        <input
          v-model="idModel"
          type="text"
          inputmode="numeric"
          autocomplete="off"
          placeholder="523607"
          aria-label="禁漫车号"
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
          <span v-for="(char, idx) in jmBtnText" :key="idx">{{ char }}</span>
        </span>
      </button>
    </form>

    <div class="download-settings__row">
      <label class="cache-check">
        <input v-model="prefetchAllModel" type="checkbox" />
        <span>同时缓存全部页面</span>
      </label>
      <Tooltip
        id="cache-all-tip"
        tip="收录时直接把所有章节与页面下载到本地磁盘（适合整本离线保存）。不勾选则仅缓存前 4 页封面，后续页面在翻阅时按需秒级懒下载。"
        side="top"
      >
        <button class="tooltip-icon" type="button" aria-label="关于缓存全部页面">
          <AppIcon name="info" size="xs" />
        </button>
      </Tooltip>
    </div>
  </div>
</template>

<style scoped>
.jm-tab-controls {
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
  color: #fff8f2;
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
  gap: 2px;
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
  padding: 2px;
  border-radius: var(--radius-1);
}

.tooltip-icon:hover {
  color: var(--accent);
}
</style>

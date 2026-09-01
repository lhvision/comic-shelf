<script setup lang="ts">
/**
 * @file ImportLocalTab.vue
 * @description 服务器本地路径扫描收录与工坊入口面板。
 *
 * 核心功能：
 * - 服务器目录路径输入与格式前缀 `PATH`；
 * - 竖排文字提交按钮（扫描中状态）；
 * - 自建图集工坊入口提示卡片。
 */

import { computed } from 'vue'

/** 绑定的本地路径输入值（v-model:localPath） */
const localPathModel = defineModel<string>('localPath', { default: '' })

const props = defineProps<{
  /** 是否正在执行本地目录扫描与收录请求 */
  localImporting: boolean
}>()

const emit = defineEmits<{
  /** 触发提交本地路径收录 */
  submit: []
  /** 跳转至自建工坊页面 */
  workshop: []
}>()

/** 竖排按钮文字 */
const localBtnText = computed(() => (props.localImporting ? '扫描中…' : '一键收录'))
</script>

<template>
  <div class="local-tab-controls">
    <form class="import-form" @submit.prevent="emit('submit')">
      <label class="field import-field">
        <span class="field-prefix">PATH</span>
        <input
          v-model="localPathModel"
          type="text"
          autocomplete="off"
          placeholder="public/tiya-frames"
          aria-label="服务器本地目录路径"
        />
      </label>
      <button
        class="import-submit-btn"
        type="submit"
        :disabled="!localPathModel.trim() || localImporting"
        aria-label="一键收录"
      >
        <span class="vertical-text">
          <span v-for="(char, idx) in localBtnText" :key="idx">{{ char }}</span>
        </span>
      </button>
    </form>

    <div class="workshop-card">
      <span class="workshop-hint">需要上传多图或编排多章节？</span>
      <button class="workshop-btn" type="button" @click="emit('workshop')">
        进入自建图集工坊 →
      </button>
    </div>
  </div>
</template>

<style scoped>
.local-tab-controls {
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

.workshop-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--paper-0);
  border: 1px dashed var(--line);
  border-radius: var(--radius-2);
}

.workshop-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.workshop-btn {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: var(--text-xs);
  font-weight: 600;
  cursor: pointer;
  padding: 0;
  white-space: nowrap;
  transition: color var(--duration-1) var(--ease-out);
}

.workshop-btn:hover {
  color: var(--accent-strong);
  text-decoration: underline;
}
</style>

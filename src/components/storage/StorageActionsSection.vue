<script setup lang="ts">
/**
 * @file StorageActionsSection.vue
 * @description 存储管理操作按钮区组件（双级清理与两步防误触危险区）。
 *
 * 核心功能：
 * - 释放漫画画页缓存（保留应用离线运行核心资源）；
 * - 彻底重置离线环境（带 5s VueUse `refAutoReset` 自动自愈的危险操作二次确认）；
 * - 暴露 `resetConfirmation()` 供浮层关闭或重开时重置确认状态。
 */

import { refAutoReset } from '@vueuse/core'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

defineProps<{
  /** 是否正在执行清理异步操作中 */
  clearing: boolean
  /** 离线漫画画页数量 */
  mangaImageCount: number
  /** 离线漫画画页字节数 */
  mangaImageBytes: number
  /** 格式化后的漫画画页大小描述 */
  mangaImageBytesFormatted: string
}>()

const emit = defineEmits<{
  /** 触发仅清理漫画画页缓存 */
  clearImages: []
  /** 触发彻底重置全部离线存储与缓存 */
  resetAll: []
}>()

/** 5秒未确认自动重置，避免手写定时器与卸载清理 */
const isConfirmingReset = refAutoReset(false, 5000)

/** 处理重置危险按钮点击（首次展开确认，二次派发事件） */
function handleResetClick() {
  if (isConfirmingReset.value) {
    isConfirmingReset.value = false
    emit('resetAll')
  } else {
    isConfirmingReset.value = true
  }
}

/** 取消重置确认 */
function cancelReset() {
  isConfirmingReset.value = false
}

/** 供外部调用的重置确认状态方法 */
function resetConfirmation() {
  isConfirmingReset.value = false
}

defineExpose({
  resetConfirmation,
})
</script>

<template>
  <footer class="storage-panel__footer">
    <AppButton
      variant="secondary"
      size="sm"
      block
      :loading="clearing"
      :disabled="mangaImageCount === 0 && mangaImageBytes === 0"
      @click="emit('clearImages')"
    >
      <template #prefix>
        <AppIcon name="trash" size="xs" :stroke-width="1.8" />
      </template>
      清理阅览图片缓存 (释放 {{ mangaImageBytesFormatted }})
    </AppButton>

    <div class="reset-wrapper" :class="{ 'is-confirming': isConfirmingReset }">
      <template v-if="!isConfirmingReset">
        <button type="button" class="reset-btn" :disabled="clearing" @click="handleResetClick">
          重置全部离线环境
        </button>
      </template>
      <template v-else>
        <div class="confirm-box">
          <span class="confirm-warning">清空所有离线资源并注销 Service Worker</span>
          <div class="confirm-actions">
            <button
              type="button"
              class="confirm-btn danger"
              :disabled="clearing"
              @click="handleResetClick"
            >
              确认彻底重置
            </button>
            <button type="button" class="confirm-btn cancel" @click="cancelReset">取消</button>
          </div>
        </div>
      </template>
    </div>
  </footer>
</template>

<style scoped>
.storage-panel__footer {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.reset-wrapper {
  display: flex;
  justify-content: center;
}

.reset-btn {
  background: transparent;
  border: none;
  min-height: 38px;
  padding: var(--space-1) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: color var(--duration-1) var(--ease-out);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.reset-btn:hover:not(:disabled) {
  color: var(--accent);
}

.reset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.confirm-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1-5);
  padding: var(--space-2);
  background: var(--accent-soft);
  border: 1px dashed color-mix(in oklab, var(--accent) 40%, var(--line));
  border-radius: var(--radius-1);
  width: 100%;
}

.confirm-warning {
  font-size: var(--text-caption);
  color: var(--accent-strong);
  text-align: center;
}

.confirm-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.confirm-btn {
  padding: 0.25rem 0.65rem;
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  cursor: pointer;
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.confirm-btn.danger {
  background: var(--accent);
  color: #fff;
  border: 1px solid var(--accent-strong);
}

.confirm-btn.danger:hover {
  background: var(--accent-strong);
}

.confirm-btn.cancel {
  background: var(--paper-1);
  border: 1px solid var(--line);
  color: var(--ink-1);
}

.confirm-btn.cancel:hover {
  background: var(--paper-2);
  color: var(--ink-0);
}

@media (prefers-reduced-motion: reduce) {
  .confirm-btn {
    transition: none !important;
  }
}
</style>

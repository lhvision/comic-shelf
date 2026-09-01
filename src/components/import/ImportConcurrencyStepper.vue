<script setup lang="ts">
/**
 * @file ImportConcurrencyStepper.vue
 * @description 漫画画页下载并发控制步进器组件。
 *
 * 核心功能：
 * - 并发路数展示（1~12 路/次）；
 * - 增加/减少步进按钮（支持 View Transition 扩散原点传递）；
 * - 环境变量 `COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS` 锁定时呈现只读锁定提示与说明。
 */

import { useTemplateRef } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import AppIcon from '@/components/AppIcon.vue'

const props = defineProps<{
  /** 当前并发路数数值 */
  concurrency: number
  /** 允许调节的最小并发数 */
  min: number
  /** 允许调节的最大并发数 */
  max: number
  /** 是否处于设置保存异步加载中 */
  loading: boolean
  /** 是否已被服务器环境变量硬性锁定（锁定后禁止界面修改） */
  envControlled: boolean
}>()

const emit = defineEmits<{
  /** 触发减少并发 */
  dec: [el: HTMLElement | null]
  /** 触发增加并发 */
  inc: [el: HTMLElement | null]
}>()

const stepperRef = useTemplateRef<HTMLElement>('stepperRef')

/** 派发减少并发事件并传递当前步进器 DOM 节点 */
function handleDec() {
  emit('dec', stepperRef.value)
}

/** 派发增加并发事件并传递当前步进器 DOM 节点 */
function handleInc() {
  emit('inc', stepperRef.value)
}
</script>

<template>
  <div class="concurrency-wrapper">
    <div class="download-settings__row">
      <span class="download-settings__title">下载并发</span>
      <Tooltip
        id="concurrency-tip"
        tip="同时下载的页数：调大缓存更快，太高容易被 CDN 限流拖慢服务。"
        side="top"
      >
        <button class="tooltip-icon" type="button" aria-label="关于下载并发">
          <AppIcon name="info" size="xs" />
        </button>
      </Tooltip>

      <div
        v-if="!envControlled"
        ref="stepperRef"
        class="stepper"
        role="group"
        aria-label="同时下载页数"
      >
        <button
          class="stepper__btn"
          type="button"
          :disabled="concurrency <= min || loading"
          aria-label="减少下载并发"
          @click="handleDec"
        >
          −
        </button>
        <span class="stepper__value">{{ concurrency }}</span>
        <button
          class="stepper__btn"
          type="button"
          :disabled="concurrency >= max || loading"
          aria-label="增加下载并发"
          @click="handleInc"
        >
          ＋
        </button>
      </div>

      <span v-else class="stepper__value stepper__value--locked">{{ concurrency }}</span>
      <span class="download-settings__unit">路 / 次</span>
    </div>
    <p v-if="envControlled" class="download-settings__locked">
      已由环境变量 <code>COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS</code> 锁定，界面不可改。
    </p>
  </div>
</template>

<style scoped>
.concurrency-wrapper {
  display: flex;
  flex-direction: column;
}

.download-settings__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 1.8rem;
}

.download-settings__title {
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.download-settings__unit {
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.stepper {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  background: var(--paper-0);
  overflow: hidden;
  height: 1.8rem;
}

.stepper__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.6rem;
  height: 100%;
  border: 0;
  background: transparent;
  color: var(--ink-1);
  font-size: var(--text-sm);
  cursor: pointer;
  user-select: none;
  transition: all var(--duration-1) var(--ease-out);
}

.stepper__btn:hover:not(:disabled) {
  background: var(--paper-1);
  color: var(--accent);
}

.stepper__btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.stepper__value {
  min-width: 1.8rem;
  padding: 0 var(--space-1);
  text-align: center;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-0);
}

.stepper__value--locked {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
}

.download-settings__locked {
  margin-top: var(--space-1);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.download-settings__locked code {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--ink-1);
  background: var(--paper-1);
  padding: 0.1rem 0.25rem;
  border-radius: var(--radius-1);
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

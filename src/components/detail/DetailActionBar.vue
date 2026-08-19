<script setup lang="ts">
import { ref } from 'vue'
import { onClickOutside, useEventListener } from '@vueuse/core'

/**
 * 详情页操作栏 —— 阅读/缓存/刷新/移除 的动作集合 + 缓存进度条。
 * 纯展示组件：需要父级配合的值由 props 传入，动作以 emit 上抛。
 *
 * 主次层级（票据 02）：只有「继续阅读」是主按钮；其余动作统一为次级
 * btn-ghost；「移除本地」是危险动作，用朱砂危险态 + 分隔间距明显隔离。
 *
 * 危险确认（票据 01）：点「移除本地」不弹浏览器原生 confirm，而是就地展开
 * 一块纸面/朱砂风格的内联确认条（显示作品名 + 不可撤销后果），
 * 确认才 emit('removeComic')；Esc、点击外部、取消均可关闭。
 */
const props = defineProps<{
  /** 作品标题（用于危险确认文案） */
  title: string
  lastRead: number
  /** 「继续阅读」按钮文案；多章节时父级会带章节定位，缺省保持旧「第 N 页」文案。 */
  lastReadLabel?: string
  cachePercent: number
  caching: boolean
  cacheComplete: boolean
  cachedPages: number
  pageCount: number
}>()

const emit = defineEmits<{
  startReading: [page?: number]
  cacheAll: []
  refreshMetadata: []
  removeComic: []
}>()

/** 是否为内联危险确认展开态 */
const confirmOpen = ref(false)

const confirmRoot = ref<HTMLElement | null>(null)
onClickOutside(confirmRoot, () => {
  confirmOpen.value = false
})

useEventListener(window, 'keydown', (event) => {
  if (event.key === 'Escape' && confirmOpen.value) confirmOpen.value = false
})

function requestRemove() {
  confirmOpen.value = true
}

function confirmRemove() {
  confirmOpen.value = false
  emit('removeComic')
}
</script>

<template>
  <div class="detail-actions">
    <div class="action-bar surface">
      <button class="btn btn-primary btn-read" type="button" @click="emit('startReading')">
        {{ lastReadLabel || (lastRead ? `继续阅读 · 第 ${lastRead} 页` : '开始阅读') }}
      </button>

      <button class="btn btn-ghost" type="button" @click="emit('startReading', 1)">
        从第 1 页开始
      </button>
      <button
        class="btn btn-ghost"
        type="button"
        :disabled="caching || cacheComplete"
        @click="emit('cacheAll')"
      >
        {{
          cacheComplete
            ? '已全部本地化'
            : caching
              ? `缓存中 ${cachePercent}%`
              : `缓存全部（已缓存 ${cachedPages}/${pageCount}）`
        }}
      </button>
      <button class="btn btn-ghost" type="button" @click="emit('refreshMetadata')">刷新资料</button>

      <button class="btn danger" type="button" @click="requestRemove">移除本地</button>
    </div>

    <div v-if="confirmOpen" ref="confirmRoot" class="danger-confirm surface" role="alertdialog">
      <div class="danger-confirm-copy">
        <p class="danger-confirm-title">移除《{{ title }}》的本地缓存？</p>
        <p class="danger-confirm-note">
          将删除这本书的全部本地页面与封面，此操作不可撤销；远端原页不受影响。
        </p>
      </div>
      <div class="danger-confirm-actions">
        <button class="btn btn-ghost" type="button" @click="confirmOpen = false">取消</button>
        <button class="btn danger" type="button" @click="confirmRemove">确认移除</button>
      </div>
    </div>

    <div class="cache-summary" aria-hidden="true">
      <span :style="{ transform: `scaleX(${cachePercent / 100})` }" />
    </div>
    <p class="cache-summary-text">
      本地缓存 {{ cachedPages }} / {{ pageCount }} 页（{{ cachePercent }}%）
    </p>
  </div>
</template>

<style scoped>
.detail-actions {
  margin-top: var(--space-5);
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-4);
}

/* 主操作唯一高权重：加一点尺寸与层级，与其余次级按钮区分 */
.btn-read {
  letter-spacing: 0.04em;
  box-shadow: var(--shadow-1);
}

/* 危险操作：朱砂态 + 分隔间距，与其他操作清晰隔离 */
.danger {
  color: var(--accent-strong);
  border: 1px solid color-mix(in oklab, var(--accent) 35%, transparent);
}

.danger:hover {
  background: var(--accent-soft);
}

@media (min-width: 681px) {
  .action-bar .danger {
    margin-left: auto;
  }
}

.danger-confirm {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-top: var(--space-3);
  padding: var(--space-4);
  border-color: color-mix(in oklab, var(--accent) 35%, transparent);
  background: color-mix(in oklab, var(--accent) 6%, var(--paper-0));
}

.danger-confirm-title {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-0);
}

.danger-confirm-note {
  margin-top: var(--space-1);
  color: var(--ink-1);
  font-size: var(--text-xs);
  line-height: 1.6;
}

.danger-confirm-actions {
  display: flex;
  gap: var(--space-2);
}

.cache-summary {
  height: 4px;
  margin-top: var(--space-3);
  border-radius: 999px;
  background: var(--paper-2);
  overflow: hidden;
}

.cache-summary span {
  display: block;
  width: 100%;
  height: 100%;
  background: var(--accent);
  transform-origin: 0 50%;
  transition: transform var(--duration-3) var(--ease-out);
}

.cache-summary-text {
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  text-align: right;
}
</style>

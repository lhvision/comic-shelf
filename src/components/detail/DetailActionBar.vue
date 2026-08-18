<script setup lang="ts">
/**
 * 详情页操作栏 —— 阅读/缓存/刷新/移除 的动作集合 + 缓存进度条。
 * 纯展示组件：所有需要父级配合的值（lastRead/cachePercent/…）由 props 传入，
 * 动作统一以 emit 上抛，不直接调用 store/API。
 */
defineProps<{
  lastRead: number
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
</script>

<template>
  <div class="detail-actions">
    <div class="action-bar surface">
      <button class="btn btn-primary" type="button" @click="emit('startReading')">
        {{ lastRead ? `继续阅读 · 第 ${lastRead} 页` : '开始阅读' }}
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
      <button class="btn btn-ghost danger" type="button" @click="emit('removeComic')">
        移除本地
      </button>
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

.danger {
  color: var(--accent-strong);
  border-color: color-mix(in oklab, var(--accent) 35%, transparent);
}

.danger:hover {
  background: var(--accent-soft);
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

<script setup lang="ts">
/**
 * @file StoragePwaCard.vue
 * @description PWA Prompt 模式新版本卷本装订就绪提示卡片。
 */

import AppIcon from '@/components/AppIcon.vue'

defineProps<{
  /** 是否检测到新版本 Service Worker 等待激活 */
  needRefresh: boolean
  /** 是否正在执行更新重载中 */
  isUpdating: boolean
}>()

const emit = defineEmits<{
  /** 触发更新并重新装订 */
  update: []
}>()
</script>

<template>
  <section v-if="needRefresh" class="storage-update-card" aria-label="应用更新">
    <div class="update-card-left">
      <span class="update-pill font-mono">UPD</span>
      <div class="update-card-text">
        <strong class="update-card-title">新卷本装订就绪</strong>
        <small class="update-card-sub">应用最新功能与静态补丁</small>
      </div>
    </div>
    <button type="button" class="update-card-btn" :disabled="isUpdating" @click="emit('update')">
      <AppIcon
        name="refresh"
        size="xs"
        :stroke-width="1.8"
        :class="{ 'is-spinning': isUpdating }"
      />
      <span>{{ isUpdating ? '装订中…' : '立即装订' }}</span>
    </button>
  </section>
</template>

<style scoped>
.storage-update-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2-5);
  border: 1px solid color-mix(in oklab, var(--accent) 45%, var(--line));
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--accent-soft) 40%, var(--paper-0));
}

.update-card-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.update-pill {
  display: inline-grid;
  place-items: center;
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-1);
  background: var(--accent);
  color: var(--paper-0);
  font-size: var(--text-caption);
  font-weight: 600;
  line-height: 1;
  flex: 0 0 auto;
}

.update-card-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.update-card-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-0);
  line-height: var(--leading-tight);
}

.update-card-sub {
  font-size: 0.625rem;
  color: var(--ink-2);
  line-height: 1.2;
}

.update-card-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: var(--control-xs);
  padding: 0 var(--space-2-5);
  border: 1px solid color-mix(in oklab, var(--accent) 60%, transparent);
  border-radius: var(--radius-1);
  background: var(--accent);
  color: var(--paper-0);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  flex: 0 0 auto;
  transition: all var(--duration-1) var(--ease-out);
}

.update-card-btn:hover:not(:disabled) {
  background: var(--accent-strong);
}

.update-card-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>

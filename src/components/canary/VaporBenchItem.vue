<script setup lang="ts">
/**
 * @file VaporBenchItem.vue
 * @description 基准跑分对照项 —— Vue 3.6 Vapor Mode 无虚拟 DOM 微粒响应式直驱。
 */
defineProps<{
  id: number
  title: string
  progress: number
  active: boolean
}>()
</script>

<template vapor>
  <div class="bench-item" :class="{ 'is-active': active }">
    <div class="bench-item-head">
      <span class="bench-item-id">#{{ id }}</span>
      <span class="bench-item-title">{{ title }}</span>
      <span class="bench-item-val">{{ progress }}%</span>
    </div>
    <div class="bench-item-track">
      <div class="bench-item-fill" :style="{ width: `${progress}%` }" />
    </div>
  </div>
</template>

<style scoped>
.bench-item {
  padding: var(--space-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  background: var(--paper-1);
  font-size: var(--text-xs);
  contain: content;
}

.bench-item.is-active {
  border-color: var(--accent);
}

.bench-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-1);
}

.bench-item-id {
  font-family: var(--font-mono);
  color: var(--ink-2);
}

.bench-item-title {
  font-weight: 500;
  color: var(--ink-0);
}

.bench-item-val {
  font-family: var(--font-mono);
  color: var(--accent);
  font-weight: 600;
}

.bench-item-track {
  height: 4px;
  background: var(--paper-2);
  border-radius: 999px;
  overflow: hidden;
}

.bench-item-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.05s linear;
}
</style>

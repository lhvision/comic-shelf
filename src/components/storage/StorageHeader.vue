<script setup lang="ts">
/**
 * @file StorageHeader.vue
 * @description 存储管理浮层头部组件（展示标题与 PWA 独立桌面应用安装入口）。
 */

import AppIcon from '@/components/AppIcon.vue'

defineProps<{
  /** 浏览器是否支持并触发了 PWA 安装提示 */
  canInstall: boolean
  /** 当前是否已在 Standalone 独立视口运行 */
  isStandalone: boolean
}>()

const emit = defineEmits<{
  /** 点击安装桌面应用事件 */
  install: []
}>()
</script>

<template>
  <header class="storage-panel__header">
    <div class="header-titles">
      <h3 class="panel-title">阅览室设备与离线</h3>
      <span class="panel-subtitle font-mono">LOCAL STORAGE &amp; PWA</span>
    </div>

    <div class="header-action">
      <button
        v-if="canInstall"
        type="button"
        class="pwa-install-btn"
        title="将纸间添加至主屏幕或桌面独立运行"
        @click="emit('install')"
      >
        <AppIcon name="download" size="xs" :stroke-width="1.8" />
        <span>安装至桌面</span>
      </button>
      <span v-else-if="isStandalone" class="pwa-standalone-pill"> 〔 独立应用 〕 </span>
    </div>
  </header>
</template>

<style scoped>
.storage-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.panel-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-0);
  line-height: 1.2;
}

.panel-subtitle {
  display: block;
  font-size: 0.625rem;
  color: var(--ink-2);
  letter-spacing: 0.04em;
  margin-top: 1px;
}

.pwa-install-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0.2rem 0.5rem;
  border: 1px solid color-mix(in oklab, var(--accent) 35%, var(--line));
  border-radius: var(--radius-1);
  background: var(--accent-soft);
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.pwa-install-btn:hover {
  background: color-mix(in oklab, var(--accent) 22%, var(--paper-0));
  border-color: var(--accent);
}

.pwa-standalone-pill {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

@media (prefers-reduced-motion: reduce) {
  .pwa-install-btn {
    transition: none !important;
  }
}
</style>

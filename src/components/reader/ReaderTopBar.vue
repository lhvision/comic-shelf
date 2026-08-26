<script setup lang="ts">
/**
 * 阅读器顶栏 —— 返回按钮 + 书名 + 设置/全屏工具。
 * 纯展示组件：所有动作通过 emit 交给 ReaderView 处理，自身不感知路由。
 * 按钮复用 ReaderButton（票据 05：与设置面板共用同一套控件样式）。
 */
import ReaderButton from '@/components/reader/ReaderButton.vue'

defineProps<{
  title: string
  displayId: string
  /** 当前章节文案（如「第 2 話 · 标题」）；单章节作品为空字符串。 */
  chapter?: string
  hidden: boolean
}>()

defineEmits<{
  back: []
  openSettings: []
  toggleFullscreen: []
}>()
</script>

<template>
  <div class="reader-chrome" :data-hidden="hidden" :inert="hidden">
    <div class="reader-topbar">
      <ReaderButton @click="$emit('back')">← 返回</ReaderButton>
      <div class="reader-title" :title="`${title} (${displayId}${chapter ? ' · ' + chapter : ''})`">
        <strong :title="title">{{ title }}</strong>
        <span>{{ displayId }}</span>
        <span v-if="chapter" class="reader-chapter" :title="chapter">{{ chapter }}</span>
      </div>
      <div class="reader-tools">
        <ReaderButton @click="$emit('openSettings')">设置</ReaderButton>
        <ReaderButton @click="$emit('toggleFullscreen')">全屏</ReaderButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reader-chrome {
  position: absolute;
  inset: 0 0 auto;
  z-index: 5;
  background: linear-gradient(var(--reader-scrim-strong), transparent);
  transition:
    opacity var(--duration-2) var(--ease-out),
    translate var(--duration-2) var(--ease-out),
    visibility 0s;
}

.reader-chrome[data-hidden='true'] {
  opacity: 0;
  translate: 0 -100%;
  visibility: hidden;
  pointer-events: none;
  /* 先淡出再隐藏，避免渐隐时被中间态的 opacity 泄漏截断 */
  transition:
    opacity var(--duration-2) var(--ease-out),
    translate var(--duration-2) var(--ease-out),
    visibility 0s var(--duration-2);
}

.reader-topbar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-4);
  min-height: var(--header-h);
  padding: 0 var(--page-pad);
}

.reader-title {
  min-width: 0;
  display: grid;
}

.reader-title strong {
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reader-title span {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reader-title .reader-chapter::before {
  content: ' · ';
}

.reader-tools {
  display: flex;
  gap: var(--space-2);
}

@media (max-width: 680px) {
  .reader-topbar {
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: var(--space-2);
    padding-inline: var(--space-2);
  }

  .reader-tools {
    gap: var(--space-1);
  }
}
</style>

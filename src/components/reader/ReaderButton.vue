<script setup lang="ts">
/**
 * 阅读器通用按钮 —— 顶栏与设置面板共用的同款控件（票据 05 去重）。
 * 纯展示：只负责样式与焦点，动作由父级在默认插槽外通过原生事件或
 * v-on 直接绑定到根元素（attrs 自动落到 <button> 上）。
 */
defineOptions({ inheritAttrs: false })
</script>

<template>
  <button v-bind="$attrs" class="reader-btn" type="button"><slot /></button>
</template>

<style scoped>
.reader-btn {
  min-height: var(--control-md);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--reader-line-strong);
  border-radius: var(--radius-2);
  background: var(--reader-scrim-soft);
  color: var(--reader-ink);
  font-size: var(--text-xs);
  transition: background-color var(--duration-1) var(--ease-out);
}

.reader-btn:hover {
  background: var(--reader-surface-hover);
}

@media (max-width: 680px) {
  .reader-btn {
    padding: var(--space-1) var(--space-2);
  }
}
</style>

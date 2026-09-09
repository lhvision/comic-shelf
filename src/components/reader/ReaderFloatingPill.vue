<script setup lang="ts">
/**
 * @file ReaderFloatingPill.vue
 * @description 阅读器浮动画卷页标组件（条漫无缝拼接模式下的非侵入式页码浮标）。
 *
 * 核心契约：
 * 1. 替代行内占位页脚，避免腰斩条漫切片画面与对白气泡；
 * 2. 位于视口右下角，滚动时感应淡入，静止 1.5 秒后平滑淡出；
 * 3. 呼出全局 HUD 或设置面板时自动隐退，避免视觉重叠。
 */

export interface ReaderFloatingPillProps {
  /** 当前章内或全书相对页码 */
  current: number
  /** 当前章节或全书总页数 */
  total: number
  /** 是否处于滚动活跃唤醒态 */
  active: boolean
  /** 是否受外部状态压制隐退（如全局 HUD 唤醒时） */
  suppressed?: boolean
}

const props = withDefaults(defineProps<ReaderFloatingPillProps>(), {
  suppressed: false,
})
</script>

<template>
  <div
    class="reader-floating-pill"
    :data-visible="props.active && !props.suppressed"
    :aria-hidden="!props.active || props.suppressed"
  >
    <span class="pill-number current">{{ String(props.current).padStart(3, '0') }}</span>
    <span class="pill-divider" aria-hidden="true">/</span>
    <span class="pill-number total">{{ String(props.total).padStart(3, '0') }}</span>
  </div>
</template>

<style scoped>
.reader-floating-pill {
  position: absolute;
  right: max(var(--space-4), env(safe-area-inset-right));
  bottom: max(var(--space-5), env(safe-area-inset-bottom));
  z-index: 5;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--reader-line-strong);
  border-radius: 999px;
  background: var(--reader-scrim);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted);
  letter-spacing: 0.1em;
  pointer-events: none;
  user-select: none;
  opacity: 0;
  translate: 0 var(--space-2);
  transition:
    opacity var(--duration-2) var(--ease-out),
    translate var(--duration-2) var(--ease-out);
}

.reader-floating-pill[data-visible='true'] {
  opacity: 0.92;
  translate: 0 0;
}

.pill-number.current {
  color: var(--reader-ink);
  font-weight: 600;
}

.pill-divider {
  opacity: 0.5;
  font-weight: 300;
}

.pill-number.total {
  opacity: 0.75;
}
</style>

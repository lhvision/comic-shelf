<script setup lang="ts">
/**
 * @file SearchCommandChip.vue
 * @description 搜索框命令胶囊微件（朱砂印章典藏质感）。
 *
 * 核心特性：
 * 1. 明确标识当前输入框处于专注命令状态（如台词、车号、作者）；
 * 2. 具备零 DOM 抖动、零外溢排版，内联嵌入于搜索输入框左侧；
 * 3. 支持无障碍键盘焦点与点击一键退出命令模式。
 */

import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import type { SearchCommandType } from '@/composables/useSearchCommands'

const props = defineProps<{
  command: SearchCommandType
  label: string
}>()

const emit = defineEmits<{
  clear: []
}>()

const commandIcons: Record<SearchCommandType, string> = {
  dialogue: 'message-square',
  id: 'book-open',
  author: 'users',
  random: 'refresh',
}
</script>

<template>
  <div class="search-command-chip" :class="`is-${props.command}`">
    <div class="chip-badge">
      <AppIcon
        :name="commandIcons[props.command] || 'message-square'"
        size="xs"
        class="chip-icon"
      />
      <span class="chip-label">{{ props.label }}</span>
    </div>
    <AppButton
      shape="circle"
      variant="ghost"
      size="xs"
      icon="close"
      class="chip-clear-btn"
      :aria-label="`退出 ${props.label} 模式`"
      :title="`退出 ${props.label} 模式 (Backspace)`"
      @click.stop="emit('clear')"
    />
  </div>
</template>

<style scoped>
.search-command-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: color-mix(in oklab, var(--accent) 10%, var(--paper-1));
  border: 1px solid color-mix(in oklab, var(--accent) 32%, var(--line));
  border-radius: var(--radius-pill);
  padding: 0 var(--space-1) 0 var(--space-2);
  height: 2.4rem;
  flex-shrink: 0;
  user-select: none;
  animation: chip-enter var(--duration-1) var(--ease-out);
}

.chip-badge {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--accent);
}

.chip-icon {
  width: 1.2rem;
  height: 1.2rem;
  stroke-width: 2.2;
}

.chip-label {
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.chip-clear-btn {
  position: relative;
  color: var(--ink-2);
  width: 1.6rem;
  height: 1.6rem;
}

/* 扩展触控响应区至 44px 满足 WCAG 2.5.5 / Apple HIG 标准 */
.chip-clear-btn::before {
  content: '';
  position: absolute;
  inset: -10px;
}

.chip-clear-btn:hover {
  color: var(--accent);
  background: color-mix(in oklab, var(--accent) 16%, transparent);
}

@keyframes chip-enter {
  from {
    opacity: 0;
    transform: scale(0.92);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>

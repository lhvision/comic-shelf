<script setup lang="ts">
/**
 * @file SearchHistoryMenu.vue
 * @description 搜索框最近搜索历史浮层。
 *
 * 核心特性：
 * 1. 当搜索框获得焦点且输入内容为空时展开，展示最近搜索关键词；
 * 2. 支持快捷指令印章徽记（如 〔 台词 〕、〔 作者 〕），一键复用对应检索模式；
 * 3. 严格遵循 WAI-ARIA Listbox 无障碍契约，支持键盘焦点导航与回车点选；
 * 4. 提供单条删除（×）与底部/顶部一键清空历史。
 */

import { nextTick, useTemplateRef, watch } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import type { SearchHistoryItem } from '@/composables/useSearchHistory'
import { AVAILABLE_COMMANDS } from '@/composables/useSearchCommands'

const focusedIndex = defineModel<number>('focusedIndex', { default: 0 })

const props = defineProps<{
  open: boolean
  history: SearchHistoryItem[]
}>()

const emit = defineEmits<{
  select: [item: SearchHistoryItem]
  remove: [id: string]
  clear: []
}>()

const menuListRef = useTemplateRef<HTMLElement>('menuListRef')

watch(focusedIndex, async (idx) => {
  if (idx === undefined || idx < 0) return
  await nextTick()
  const list = menuListRef.value
  if (!list) return
  const activeEl = list.querySelector<HTMLElement>(`#history-opt-${idx}`)
  if (activeEl && typeof activeEl.scrollIntoView === 'function') {
    activeEl.scrollIntoView({ block: 'nearest' })
  }
})

function getCommandLabel(cmdId?: string | null): string {
  if (!cmdId) return ''
  const found = AVAILABLE_COMMANDS.find((c) => c.id === cmdId)
  return found?.label || cmdId
}

function onMouseEnter(idx: number) {
  focusedIndex.value = idx
}

function onClickItem(item: SearchHistoryItem) {
  emit('select', item)
}
</script>

<template>
  <Transition name="menu-fade">
    <div v-if="props.open" class="history-menu-popover" aria-label="搜索历史选单">
      <div class="menu-header">
        <div class="header-left">
          <AppIcon name="search" size="xs" class="header-icon" />
          <span class="header-title">最近搜索</span>
        </div>
        <div class="header-right">
          <button
            v-if="props.history.length > 0"
            type="button"
            tabindex="-1"
            class="clear-all-btn"
            aria-label="清空全部搜索历史"
            @click.stop="emit('clear')"
          >
            <AppIcon name="trash" size="xs" />
            <span>清空</span>
          </button>
        </div>
      </div>

      <div
        id="search-history-menu"
        ref="menuListRef"
        class="menu-list"
        role="listbox"
        aria-label="搜索历史列表"
      >
        <div
          v-for="(item, idx) in props.history"
          :id="`history-opt-${idx}`"
          :key="item.id"
          class="menu-item"
          :class="{ 'is-focused': focusedIndex === idx }"
          role="option"
          :aria-selected="focusedIndex === idx"
          @mouseenter="onMouseEnter(idx)"
          @click="onClickItem(item)"
        >
          <div class="item-content">
            <span v-if="item.command" class="command-seal">
              {{ getCommandLabel(item.command) }}
            </span>
            <span class="item-query">{{ item.query }}</span>
          </div>

          <div class="item-actions">
            <button
              type="button"
              tabindex="-1"
              class="delete-btn"
              :aria-label="`删除 ${item.query} (Delete)`"
              :title="`删除 ${item.query} (Delete)`"
              @click.stop="emit('remove', item.id)"
            >
              <AppIcon name="close" size="xs" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.history-menu-popover {
  position: absolute;
  top: calc(100% + var(--space-2));
  left: 0;
  right: 0;
  width: 100%;
  max-width: min(34rem, 100%);
  background: var(--paper-0);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  box-shadow: var(--shadow-3);
  z-index: var(--z-dropdown);
  overflow: hidden;
  user-select: none;
}

.menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  background: var(--paper-1);
  border-bottom: 1px solid var(--line);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--ink-1);
}

.header-icon {
  color: var(--accent);
}

.header-title {
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-0);
}

.header-right {
  display: flex;
  align-items: center;
}

.clear-all-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: none;
  background: transparent;
  color: var(--ink-2);
  font-size: var(--text-xs);
  cursor: pointer;
  border-radius: var(--radius-1);
  transition:
    color var(--duration-1) var(--ease-out),
    background var(--duration-1) var(--ease-out);
}

.clear-all-btn:hover {
  color: var(--danger);
  background: color-mix(in oklab, var(--danger) 10%, transparent);
}

.menu-list {
  max-height: min(18rem, 45dvh);
  overflow-y: auto;
  padding: var(--space-1) 0;
}

.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  transition: background var(--duration-1) var(--ease-out);
  gap: var(--space-2);
}

.menu-item:hover,
.menu-item.is-focused {
  background: var(--paper-warm);
}

.item-content {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.command-seal {
  display: inline-flex;
  align-items: center;
  padding: var(--space-badge-y) var(--space-badge-x);
  font-size: var(--text-caption);
  font-weight: 600;
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--accent) 12%, transparent);
  color: var(--accent-strong);
  border: 1px solid color-mix(in oklab, var(--accent) 25%, transparent);
  white-space: nowrap;
  flex-shrink: 0;
}

.item-query {
  font-size: var(--text-sm);
  color: var(--ink-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.delete-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  min-width: 1.75rem;
  min-height: 1.75rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ink-2);
  border-radius: var(--radius-1);
  cursor: pointer;
  transition:
    color var(--duration-1) var(--ease-out),
    background var(--duration-1) var(--ease-out);
}

/* 扩展移动端触控热区（满足 44×44px 规范），杜绝触屏误触父级列表项 */
.delete-btn::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  min-width: 2.75rem;
  min-height: 2.75rem;
  width: 100%;
  height: 100%;
}

.delete-btn:hover {
  color: var(--danger);
  background: color-mix(in oklab, var(--danger) 10%, transparent);
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition:
    opacity var(--duration-1) var(--ease-out),
    transform var(--duration-1) var(--ease-out);
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>

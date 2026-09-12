<script setup lang="ts">
/**
 * @file SearchCommandMenu.vue
 * @description 搜索框快捷指令选单浮层。
 *
 * 核心特性：
 * 1. 当用户在搜索框键入 '/' 时展开，展示可用快捷指令集；
 * 2. 纯声明式纸面清单排版，呈现指令名称、别名与功能说明；
 * 3. 严格遵循 WAI-ARIA Listbox 无障碍标准，支持键盘焦点导航与回车/Tab 补全；
 * 4. 纸间水墨质感与朱砂提示徽印。
 */

import { nextTick, ref, watch } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import type { SearchCommandDef } from '@/composables/useSearchCommands'

const props = withDefaults(
  defineProps<{
    open: boolean
    commands: SearchCommandDef[]
    focusedIndex?: number
  }>(),
  {
    focusedIndex: 0,
  },
)

const emit = defineEmits<{
  select: [cmd: SearchCommandDef]
  close: []
  'update:focusedIndex': [index: number]
}>()

const menuListRef = ref<HTMLElement | null>(null)

watch(
  () => props.focusedIndex,
  async (idx) => {
    if (idx === undefined || idx < 0 || !menuListRef.value) return
    await nextTick()
    const activeEl = menuListRef.value.querySelector<HTMLElement>(`#cmd-opt-${idx}`)
    if (activeEl && typeof activeEl.scrollIntoView === 'function') {
      activeEl.scrollIntoView({ block: 'nearest' })
    }
  },
)

function onMouseEnter(idx: number) {
  emit('update:focusedIndex', idx)
}

function onClickItem(cmd: SearchCommandDef) {
  emit('select', cmd)
}
</script>

<template>
  <Transition name="menu-fade">
    <div v-if="props.open" class="command-menu-popover" aria-label="搜索框快捷指令">
      <div class="menu-header">
        <div class="header-left">
          <AppIcon name="search" size="xs" class="header-icon" />
          <span class="header-title">快捷命令选单</span>
        </div>
        <div class="header-right">
          <kbd class="kbd-hint">↑↓ 导航</kbd>
          <kbd class="kbd-hint">Tab / ↵ 补全</kbd>
        </div>
      </div>

      <div
        id="search-command-menu"
        ref="menuListRef"
        class="menu-list"
        role="listbox"
        aria-label="快捷指令列表"
      >
        <div
          v-for="(cmd, idx) in props.commands"
          :id="`cmd-opt-${idx}`"
          :key="cmd.id"
          class="menu-item"
          :class="{ 'is-focused': props.focusedIndex === idx }"
          role="option"
          :aria-selected="props.focusedIndex === idx"
          @mouseenter="onMouseEnter(idx)"
          @click="onClickItem(cmd)"
        >
          <div class="item-tag-wrapper">
            <span class="command-tag">{{ cmd.name }}</span>
          </div>

          <div class="item-info">
            <span class="command-desc">{{ cmd.description }}</span>
            <span class="command-alias">
              别名: {{ cmd.aliases.map((a) => `/${a}`).join(', ') }}
            </span>
          </div>

          <div class="item-action" aria-hidden="true">
            <span class="action-shortcut">↵ 确认</span>
          </div>
        </div>

        <div v-if="props.commands.length === 0" class="menu-empty">
          <span>未找到匹配的快捷指令</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.command-menu-popover {
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
  z-index: var(--z-dropdown, 50);
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
  gap: var(--space-1);
}

.kbd-hint {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  font-size: var(--text-caption);
  font-family: monospace;
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  color: var(--ink-2);
}

.menu-list {
  padding: var(--space-1);
  max-height: 24rem;
  overflow-y: auto;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-1);
  cursor: pointer;
  transition:
    background var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.menu-item:hover,
.menu-item.is-focused {
  background: var(--paper-2);
}

.item-tag-wrapper {
  flex-shrink: 0;
}

.command-tag {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  background: color-mix(in oklab, var(--accent) 12%, var(--paper-1));
  border: 1px solid color-mix(in oklab, var(--accent) 30%, transparent);
  border-radius: var(--radius-1);
  color: var(--accent);
  font-family: monospace;
  font-size: var(--text-xs);
  font-weight: 700;
}

.item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.command-desc {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--ink-0);
  line-height: 1.3;
}

.command-alias {
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.item-action {
  flex-shrink: 0;
}

.action-shortcut {
  font-size: var(--text-caption);
  color: var(--ink-2);
  opacity: 0;
  transition: opacity var(--duration-1) var(--ease-out);
}

.menu-item:hover .action-shortcut,
.menu-item.is-focused .action-shortcut {
  opacity: 1;
  color: var(--accent);
}

.menu-empty {
  padding: var(--space-4);
  text-align: center;
  font-size: var(--text-xs);
  color: var(--ink-2);
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
  transform: translateY(-0.4rem);
}
</style>

<script setup lang="ts">
/**
 * AppChip.vue — 纸间通用微件胶囊组件
 *
 * @description
 * 纸间设计系统基础原子组件，用于承载分类标签（Tag）、筛选切换器（Filter Toggle）、
 * 计数值胶囊与可移除标记。根据交互属性自动在 `<span>` 与 `<button>` 间多态切换，
 * 提供典雅水墨纸质质感与无障碍（WCAG / ARIA）原生按压状态支持。
 */
import { computed, getCurrentInstance } from 'vue'
import AppIcon from '@/components/AppIcon.vue'

export interface AppChipProps {
  /** 是否处于按压/激活状态；若传入布尔值，自动升格为交互按钮模式并绑定 aria-pressed */
  pressed?: boolean
  /** 是否具有交互能力（按钮形态）；若未指定，当绑定 @click 或 pressed !== undefined 时自动判定为 true */
  interactive?: boolean
  /** 尺寸规格：标准 md (12px) 或紧凑 sm (11px) */
  size?: 'sm' | 'md'
  /** 色调变体 */
  tone?: 'default' | 'accent' | 'muted'
  /** 附属数字或文本计数，自动渲染在尾部微标中 */
  count?: number | string
  /** 前置矢量图标名称（对应 src/components/icons/） */
  icon?: string
  /** 是否可删除（开启后在尾部呈现无障碍删除按钮） */
  removable?: boolean
  /** 删除按钮的无障碍标签 */
  removeAriaLabel?: string
  /** 禁用状态 */
  disabled?: boolean
  /** 原生按钮类型，默认为 'button' */
  type?: 'button' | 'submit' | 'reset'
}

const props = withDefaults(defineProps<AppChipProps>(), {
  pressed: undefined,
  interactive: undefined,
  size: 'md',
  tone: 'default',
  count: undefined,
  icon: undefined,
  removable: false,
  removeAriaLabel: '删除',
  disabled: false,
  type: 'button',
})

const emit = defineEmits<{
  click: [event: MouseEvent]
  remove: [event: MouseEvent]
}>()

const instance = getCurrentInstance()

const hasClickListener = computed(() => {
  const vnodeProps = instance?.vnode.props
  return Boolean(vnodeProps && ('onClick' in vnodeProps || 'onclick' in vnodeProps))
})

const isInteractive = computed(() => {
  // 防御性守卫：当处于可移除状态 (removable) 时，内部包含独立的删除按钮 <button>。
  // 按照 W3C HTML5 标准，<button> 内部严禁嵌套交互元素或另一个 <button>。
  // 因此 removable 模式下根容器强制渲染为 <span>，彻底杜绝按钮嵌套非法结构。
  if (props.removable) {
    return false
  }
  if (props.interactive !== undefined) {
    return props.interactive
  }
  if (props.pressed !== undefined) {
    return true
  }
  return hasClickListener.value
})

const chipClasses = computed(() => [
  'chip',
  {
    'chip-button': isInteractive.value,
    'chip--sm': props.size === 'sm',
    'chip--removable': props.removable,
    'is-disabled': props.disabled,
  },
])

function handleClick(event: MouseEvent) {
  if (props.disabled) {
    event.preventDefault()
    return
  }
  emit('click', event)
}

function handleKeydown(event: KeyboardEvent) {
  if (isInteractive.value || !hasClickListener.value || props.disabled) return
  emit('click', event as unknown as MouseEvent)
}

function handleRemove(event: MouseEvent) {
  event.stopPropagation()
  event.preventDefault()
  if (props.disabled) return
  emit('remove', event)
}
</script>

<template>
  <component
    :is="isInteractive ? 'button' : 'span'"
    :type="isInteractive ? type : undefined"
    :class="chipClasses"
    :data-tone="tone !== 'default' ? tone : undefined"
    :disabled="isInteractive && disabled ? true : undefined"
    :role="!isInteractive && hasClickListener ? 'button' : undefined"
    :tabindex="!isInteractive && hasClickListener ? (disabled ? -1 : 0) : undefined"
    :aria-pressed="
      isInteractive && pressed !== undefined ? (pressed ? 'true' : 'false') : undefined
    "
    @click="handleClick"
    @keydown.enter.prevent="handleKeydown"
    @keydown.space.prevent="handleKeydown"
  >
    <span v-if="$slots.prefix || icon" class="chip-prefix">
      <slot name="prefix">
        <AppIcon v-if="icon" :name="icon" size="xs" />
      </slot>
    </span>

    <span class="chip-label tag-chip__text">
      <slot></slot>
    </span>

    <slot name="count">
      <small v-if="count !== undefined && count !== ''" class="tag-count">{{ count }}</small>
    </slot>

    <span v-if="$slots.suffix" class="chip-suffix">
      <slot name="suffix"></slot>
    </span>

    <button
      v-if="removable"
      type="button"
      class="chip-del-btn tag-chip__del"
      :aria-label="removeAriaLabel"
      :disabled="disabled"
      @click="handleRemove"
      @keydown.stop
    >
      <slot name="remove-icon">
        <AppIcon name="close" size="xs" :stroke-width="2.2" />
      </slot>
    </button>
  </component>
</template>

<style scoped>
.chip--sm {
  padding: 0.15rem 0.5rem;
  font-size: var(--text-caption);
  gap: 0.25em;
}

.chip-prefix,
.chip-suffix {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.chip-label {
  display: inline-flex;
  align-items: center;
}

.tag-count {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  opacity: 0.75;
}

.chip-del-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1rem;
  height: 1rem;
  margin-left: 0.1rem;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  flex-shrink: 0;
  transition:
    color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.chip-del-btn:hover {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.chip[data-tone='muted'] {
  color: var(--ink-2);
  background: color-mix(in oklab, var(--paper-1) 40%, transparent);
}

.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}
</style>

<script setup lang="ts">
import { computed, useAttrs, useSlots } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/components/icons'

export interface AppButtonProps {
  /** 视觉变体 */
  variant?: 'primary' | 'secondary' | 'ghost' | 'soft' | 'danger' | 'success'
  /** 尺寸档位 */
  size?: 'xs' | 'sm' | 'md' | 'lg'
  /** 形状外观：default (常规矩形药丸) | circle (正圆图标按钮) | square (圆角方块图标按钮) */
  shape?: 'default' | 'circle' | 'square'
  /** 主题环境：paper (亮色纸间) | reader (阅览室暗室高对比度防御) */
  theme?: 'paper' | 'reader'
  /** 图标名称（单源收敛自 src/components/icons） */
  icon?: IconName
  /** 图标位置：left (默认前缀) | right (后缀) */
  iconPosition?: 'left' | 'right'
  /** 加载中状态 */
  loading?: boolean
  /** 禁用状态 */
  disabled?: boolean
  /** 原生按钮类型（仅在渲染为原生 button 时生效） */
  type?: 'button' | 'submit' | 'reset'
  /** 是否为块级按钮（100% 宽度） */
  block?: boolean
  /** 多态路由目标，若提供则渲染为 RouterLink */
  to?: RouteLocationRaw
  /** 多态外部链接，若提供则渲染为 <a> */
  href?: string
  /** 外链打开方式 */
  target?: string
  /** 外部链接安全属性 */
  rel?: string
}

const props = withDefaults(defineProps<AppButtonProps>(), {
  variant: 'secondary',
  size: 'md',
  shape: 'default',
  theme: 'paper',
  iconPosition: 'left',
  loading: false,
  disabled: false,
  type: 'button',
  block: false,
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const slots = useSlots()
const attrs = useAttrs()

const ICON_ONLY_SIZES: Record<'xs' | 'sm' | 'md' | 'lg', 'xs' | 'sm' | 'md' | 'lg'> = {
  xs: 'xs',
  sm: 'sm',
  md: 'sm',
  lg: 'lg',
}

const BUTTON_WITH_TEXT_ICON_SIZES: Record<'xs' | 'sm' | 'md' | 'lg', 'xs' | 'sm' | 'md' | 'lg'> = {
  xs: 'xs',
  sm: 'xs',
  md: 'xs',
  lg: 'sm',
}

/** 判定是否为纯图标按钮模式（解耦外观形状与内容插槽，支持自定义图标插槽与图文并存） */
const hasCustomSlotContent = computed(() => {
  return Boolean(slots.default || slots.prefix || slots.suffix)
})

const isIconOnly = computed(() => {
  if (!hasCustomSlotContent.value) {
    return props.shape !== 'default' || Boolean(props.icon)
  }
  // 若传入默认插槽但未声明 icon 属性，且指定了正圆/方块形状（如 BackToTop 自定义插槽图标）
  if (props.shape !== 'default' && !props.icon) {
    return true
  }
  return false
})

/** 图标根据按钮尺寸与形态自适应尺寸（常量字典映射驱动） */
const iconSize = computed(() => {
  return isIconOnly.value ? ICON_ONLY_SIZES[props.size] : BUTTON_WITH_TEXT_ICON_SIZES[props.size]
})

/** 多态渲染底层组件感知 */
const isRouterLink = computed(() => Boolean(props.to))
const isAnchor = computed(() => !props.to && Boolean(props.href))
const isLink = computed(() => isRouterLink.value || isAnchor.value)

const tag = computed(() => {
  if (isRouterLink.value) return 'RouterLink'
  if (isAnchor.value) return 'a'
  return 'button'
})

const computedRel = computed(() => {
  if (props.rel) return props.rel
  if (props.target === '_blank') return 'noopener noreferrer'
  return undefined
})

const isDisabled = computed(() => props.disabled || props.loading)

const btnClasses = computed(() => [
  'btn',
  `btn-${props.variant}`,
  `btn-${props.size}`,
  {
    'btn-block': props.block,
    'is-loading': props.loading,
    'is-disabled': isDisabled.value,
    'is-icon-only': isIconOnly.value,
    [`btn-shape-${props.shape}`]: props.shape !== 'default',
    'is-reader': props.theme === 'reader',
  },
])

function handleClick(event: MouseEvent) {
  if (isDisabled.value) {
    event.preventDefault()
    event.stopPropagation()
    return
  }
  emit('click', event)
}

// 开发环境无障碍安全护栏：纯图标按钮必须提供无障碍描述
if (import.meta.env.DEV) {
  if (isIconOnly.value && !attrs['aria-label'] && !attrs['title'] && !attrs['aria-labelledby']) {
    console.warn(
      `[AppButton] 纯图标按钮必须提供 'aria-label' 或 'title' 属性以保证无障碍访问 (WCAG 4.1.2).`,
      { icon: props.icon, shape: props.shape },
    )
  }
}
</script>

<template>
  <component
    :is="tag"
    :type="tag === 'button' ? type : undefined"
    :to="to"
    :href="isDisabled ? undefined : href"
    :target="target"
    :rel="computedRel"
    :class="btnClasses"
    :disabled="tag === 'button' ? isDisabled : undefined"
    :aria-disabled="isLink && isDisabled ? 'true' : undefined"
    :tabindex="isLink && isDisabled ? -1 : undefined"
    :aria-busy="loading ? 'true' : undefined"
    @click="handleClick"
  >
    <!-- 加载中 Spinner 动效 -->
    <span v-if="loading" class="btn-spinner" aria-hidden="true"></span>

    <!-- 纯图标模式渲染 -->
    <template v-else-if="isIconOnly">
      <AppIcon v-if="icon && !$slots.default" :name="icon" :size="iconSize" />
      <slot v-else></slot>
    </template>

    <!-- 标准图文模式渲染 -->
    <template v-else>
      <span v-if="$slots.prefix || (icon && iconPosition !== 'right')" class="btn-prefix">
        <slot v-if="$slots.prefix" name="prefix"></slot>
        <AppIcon v-else-if="icon" :name="icon" :size="iconSize" />
      </span>

      <span class="btn-content">
        <slot></slot>
      </span>

      <span
        v-if="($slots.suffix || (icon && iconPosition === 'right')) && !loading"
        class="btn-suffix"
      >
        <slot v-if="$slots.suffix" name="suffix"></slot>
        <AppIcon v-else-if="icon" :name="icon" :size="iconSize" />
      </span>
    </template>
  </component>
</template>

<style scoped>
.btn-content {
  display: inline-flex;
  align-items: center;
  gap: inherit;
}

.btn-prefix,
.btn-suffix {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.btn-spinner {
  width: 1em;
  height: 1em;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
  flex-shrink: 0;
}

/* 形状外观：正圆与圆角方块 */
.btn-shape-circle,
.btn-shape-square,
.is-icon-only {
  padding: 0;
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
}

.btn-shape-circle {
  border-radius: 50%;
}

.btn-shape-square {
  border-radius: var(--radius-2);
}

/* 尺寸与宽高映射 */
.btn-shape-circle.btn-xs,
.btn-shape-square.btn-xs,
.is-icon-only.btn-xs {
  width: 1.75rem;
  height: 1.75rem;
  min-height: 1.75rem;
}

.btn-shape-circle.btn-sm,
.btn-shape-square.btn-sm,
.is-icon-only.btn-sm {
  width: var(--control-sm);
  height: var(--control-sm);
  min-height: var(--control-sm);
}

.btn-shape-circle.btn-md,
.btn-shape-square.btn-md,
.is-icon-only.btn-md {
  width: var(--control-md);
  height: var(--control-md);
  min-height: var(--control-md);
}

.btn-shape-circle.btn-lg,
.btn-shape-square.btn-lg,
.is-icon-only.btn-lg {
  width: var(--control-lg);
  height: var(--control-lg);
  min-height: var(--control-lg);
}

/* 图标按钮 ghost 变体质感（对齐旧 .icon-btn 典藏质感） */
.btn-shape-circle.btn-ghost,
.btn-shape-square.btn-ghost {
  border: 1px solid var(--line);
  background: color-mix(in oklab, var(--paper-0) 82%, transparent);
  color: var(--ink-1);
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(8px);
}

.btn-shape-circle.btn-ghost:hover:not(.is-disabled):not(:disabled),
.btn-shape-square.btn-ghost:hover:not(.is-disabled):not(:disabled) {
  transform: scale(1.06);
  background: var(--paper-0);
  border-color: var(--line-strong);
  color: var(--ink-0);
}

/* 链接多态下的禁用态表现 */
.btn.is-disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none !important;
  box-shadow: none !important;
  pointer-events: auto;
}

/* 阅读器暗室主题高对比度防御（WCAG AA 级标准） */
.btn.is-reader.btn-ghost {
  background: var(--reader-surface-strong);
  border-color: var(--reader-line-strong);
  color: var(--reader-ink);
}

.btn.is-reader.btn-ghost:hover:not(.is-disabled):not(:disabled) {
  background: var(--reader-surface-hover);
  border-color: var(--reader-line-strong);
  color: var(--reader-ink);
}

.btn.is-reader.btn-primary {
  background: var(--accent);
  color: var(--accent-contrast);
}

.btn.is-reader.btn-primary:hover:not(.is-disabled):not(:disabled) {
  background: var(--accent-strong);
}

.btn.is-reader.btn-secondary {
  background: var(--reader-surface-strong);
  color: var(--reader-ink);
  border-color: var(--reader-line-strong);
}

.btn.is-reader.btn-shape-circle.btn-ghost,
.btn.is-reader.btn-shape-square.btn-ghost {
  background: var(--reader-scrim-soft);
  border-color: var(--reader-line-strong);
  color: var(--reader-ink);
}

@media (max-width: 680px) {
  .btn-shape-circle.btn-md,
  .btn-shape-square.btn-md,
  .is-icon-only.btn-md {
    width: var(--control-sm);
    height: var(--control-sm);
    min-height: var(--control-sm);
  }
}
</style>

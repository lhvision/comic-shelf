<script setup lang="ts" generic="T extends string | number">
import { computed, nextTick, ref, useId, watch } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import AppPopover from '@/components/AppPopover.vue'
import type { DropdownOption } from '@/types'

export type { DropdownOption }

const props = withDefaults(
  defineProps<{
    options: DropdownOption<T>[]
    modelValue?: T | null
    placeholder?: string
    label?: string
    disabled?: boolean
    size?: 'sm' | 'md'
    side?: 'top' | 'bottom'
    align?: 'start' | 'end' | 'center'
    block?: boolean
    width?: string
    closeOnSelect?: boolean
    ariaLabel?: string
  }>(),
  {
    modelValue: null,
    placeholder: '请选择',
    label: undefined,
    disabled: false,
    size: 'md',
    side: 'bottom',
    align: 'start',
    block: false,
    width: undefined,
    closeOnSelect: true,
    ariaLabel: '下拉菜单',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: T]
  change: [value: T]
  select: [option: DropdownOption<T>]
}>()

const isSelectMode = computed(() => props.modelValue !== null && props.modelValue !== undefined)
const hasIcons = computed(() => props.options.some((opt) => !!opt.icon))

const selectedOption = computed(() => {
  if (!isSelectMode.value) return null
  return props.options.find((opt) => opt.key === props.modelValue) ?? null
})

const triggerText = computed(() => {
  if (isSelectMode.value && selectedOption.value) {
    return selectedOption.value.label
  }
  return props.label ?? props.placeholder
})

const isOpen = ref(false)
const popoverRef = ref<InstanceType<typeof AppPopover> | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const uid = useId().replace(/[^a-zA-Z0-9_-]+/g, '')
const listboxId = `dropdown-list-${uid}`

const activeIndex = ref<number>(-1)

function syncActiveIndex() {
  if (props.modelValue !== null && props.modelValue !== undefined) {
    activeIndex.value = props.options.findIndex((opt) => opt.key === props.modelValue)
  } else {
    activeIndex.value = props.options.findIndex((opt) => !opt.disabled && !opt.separator)
  }
}

watch(
  () => props.modelValue,
  () => syncActiveIndex(),
  { immediate: true },
)

function scrollActiveIntoView() {
  nextTick(() => {
    const activeEl = panelRef.value?.querySelector<HTMLElement>('[data-active="true"]')
    activeEl?.scrollIntoView?.({ block: 'nearest' })
  })
}

watch(isOpen, (open) => {
  if (open) {
    syncActiveIndex()
    scrollActiveIntoView()
  }
})

watch(activeIndex, () => {
  if (isOpen.value) {
    scrollActiveIntoView()
  }
})

function moveBy(step: number) {
  const len = props.options.length
  if (len === 0) return
  let idx = activeIndex.value
  for (let i = 0; i < len; i++) {
    idx = (idx + step + len) % len
    const opt = props.options[idx]
    if (opt && !opt.disabled && !opt.separator) {
      activeIndex.value = idx
      return
    }
  }
}

function moveToFirst() {
  for (let i = 0; i < props.options.length; i++) {
    const opt = props.options[i]
    if (opt && !opt.disabled && !opt.separator) {
      activeIndex.value = i
      return
    }
  }
}

function moveToLast() {
  for (let i = props.options.length - 1; i >= 0; i--) {
    const opt = props.options[i]
    if (opt && !opt.disabled && !opt.separator) {
      activeIndex.value = i
      return
    }
  }
}

function selectOption(option: DropdownOption<T>) {
  if (option.disabled || option.separator) return
  emit('select', option)
  if (props.modelValue !== undefined) {
    emit('update:modelValue', option.key)
    emit('change', option.key)
  }
  if (props.closeOnSelect) {
    isOpen.value = false
  }
}

function onTriggerKeydown(event: KeyboardEvent) {
  if (props.disabled) return
  const key = event.key
  if (!isOpen.value) {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' ', 'Spacebar'].includes(key)) {
      event.preventDefault()
      isOpen.value = true
    }
    return
  }

  if (key === 'ArrowDown') {
    event.preventDefault()
    moveBy(1)
  } else if (key === 'ArrowUp') {
    event.preventDefault()
    moveBy(-1)
  } else if (key === 'Home') {
    event.preventDefault()
    moveToFirst()
  } else if (key === 'End') {
    event.preventDefault()
    moveToLast()
  } else if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
    event.preventDefault()
    const activeOpt = props.options[activeIndex.value]
    if (activeOpt) selectOption(activeOpt)
  } else if (key === 'Escape' || key === 'Tab') {
    isOpen.value = false
  }
}
</script>

<template>
  <AppPopover
    ref="popoverRef"
    v-model:open="isOpen"
    :side="side"
    :align="align"
    :disabled="disabled"
    :width="width"
    class="app-dropdown-root"
    :class="{
      'is-block': block,
      'is-disabled': disabled,
      [`is-${size}`]: true,
    }"
  >
    <template #default="{ open, targetId }">
      <slot
        name="trigger"
        :open="open"
        :selected="selectedOption"
        :label="triggerText"
        :target-id="targetId"
      >
        <button
          class="dropdown-trigger btn"
          :class="{
            'is-open': open,
            [`btn-${size}`]: true,
          }"
          type="button"
          :aria-haspopup="'listbox'"
          :aria-expanded="open"
          :aria-controls="listboxId"
          :disabled="disabled"
          :title="triggerText"
          @keydown="onTriggerKeydown"
        >
          <slot name="leading" :selected="selectedOption">
            <AppIcon
              v-if="selectedOption?.icon"
              :name="selectedOption.icon"
              :size="size === 'sm' ? 'xs' : 'sm'"
            />
          </slot>

          <span class="trigger-label">{{ triggerText }}</span>

          <AppIcon class="chevron" name="chevron-down" size="xs" />
        </button>
      </slot>
    </template>

    <template #content="{ close }">
      <div
        :id="listboxId"
        ref="panelRef"
        class="dropdown-menu-panel"
        :role="isSelectMode ? 'listbox' : 'menu'"
        :aria-label="ariaLabel"
        tabindex="-1"
        @keydown="onTriggerKeydown"
      >
        <template v-for="(option, idx) in options" :key="String(option.key)">
          <hr v-if="option.separator" class="dropdown-divider" />
          <button
            v-else
            type="button"
            :role="isSelectMode ? 'option' : 'menuitem'"
            class="dropdown-item"
            :class="{
              'is-active': idx === activeIndex,
              'is-selected': option.key === modelValue || option.checked === true,
              'is-danger': option.danger,
              'is-disabled': option.disabled,
            }"
            :data-active="idx === activeIndex"
            :aria-selected="
              isSelectMode ? option.key === modelValue || option.checked === true : undefined
            "
            :disabled="option.disabled"
            :title="option.hint ? `${option.label} (${option.hint})` : option.label"
            @click="selectOption(option)"
            @mouseenter="!option.disabled && (activeIndex = idx)"
          >
            <!-- 勾选指示器 / 图标（仅在选择模式或有图标时保留前导空间） -->
            <span v-if="isSelectMode || hasIcons" class="item-leading">
              <AppIcon
                v-if="option.key === modelValue || option.checked === true"
                class="item-check"
                name="check"
                size="sm"
              />
              <AppIcon v-else-if="option.icon" class="item-icon" :name="option.icon" size="sm" />
              <span v-else class="item-leading-placeholder" />
            </span>

            <span class="item-body">
              <span class="item-label">{{ option.label }}</span>
              <small v-if="option.sub" class="item-sub">{{ option.sub }}</small>
            </span>

            <small v-if="option.hint" class="item-hint">{{ option.hint }}</small>
          </button>
        </template>
      </div>
    </template>
  </AppPopover>
</template>

<style scoped>
.app-dropdown-root {
  display: inline-flex;
}

.app-dropdown-root.is-block {
  display: flex;
  width: 100%;
}

.app-dropdown-root.is-block :deep(.app-popover-trigger),
.app-dropdown-root.is-block .dropdown-trigger {
  width: 100%;
}

.dropdown-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0) 86%, var(--paper-1));
  color: var(--ink-0);
  font-size: var(--text-sm);
  font-family: var(--font-body);
  white-space: nowrap;
  user-select: none;
  cursor: pointer;
  box-sizing: border-box;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out);
}

.dropdown-trigger:hover:not(:disabled) {
  border-color: var(--line-strong);
  background: var(--paper-0);
}

.dropdown-trigger:focus-visible,
.dropdown-trigger.is-open {
  border-color: var(--accent);
  background: var(--paper-0);
  box-shadow: 0 0 0 3px var(--accent-soft);
  outline: none;
}

.dropdown-trigger.btn-md {
  min-height: var(--control-md);
  padding: 0.45rem 0.85rem 0.45rem 1rem;
}

.dropdown-trigger.btn-sm {
  min-height: var(--control-sm);
  padding: 0.25rem 0.65rem 0.25rem 0.75rem;
  font-size: var(--text-xs);
}

.dropdown-trigger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.trigger-label {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}

.chevron {
  flex: 0 0 auto;
  color: var(--ink-2);
  transition: transform var(--duration-2) var(--ease-out);
}

.dropdown-trigger.is-open .chevron {
  transform: rotate(180deg);
}

.dropdown-menu-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-0-5);
  min-width: 10rem;
  outline: none;
}

.dropdown-divider {
  border: 0;
  border-top: 1px solid var(--line);
  margin: var(--space-1) 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: 0.45rem 0.75rem;
  border: 0;
  border-radius: var(--radius-1);
  background: transparent;
  color: var(--ink-1);
  font-size: var(--text-sm);
  font-family: var(--font-body);
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
  box-sizing: border-box;
  transition:
    background-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.dropdown-item:hover:not(:disabled),
.dropdown-item.is-active:not(:disabled) {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.dropdown-item.is-selected {
  color: var(--accent-strong);
  font-weight: 600;
}

.dropdown-item.is-danger {
  color: var(--danger);
}

.dropdown-item.is-danger:hover:not(:disabled),
.dropdown-item.is-danger.is-active:not(:disabled) {
  background: var(--danger-soft);
  color: var(--danger);
}

.dropdown-item:disabled,
.dropdown-item.is-disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.item-leading {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15rem;
  height: 1.15rem;
  flex: 0 0 auto;
}

.item-check {
  color: var(--accent);
}

.item-icon {
  color: var(--ink-2);
}

.item-leading-placeholder {
  width: 1.15rem;
  height: 1.15rem;
  flex: 0 0 auto;
}

.item-body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.item-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-sub {
  font-size: var(--text-caption);
  font-family: var(--font-mono);
  color: var(--ink-2);
}

.item-hint {
  flex: 0 0 auto;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--ink-2);
  margin-left: var(--space-2);
}

@media (prefers-reduced-motion: reduce) {
  .dropdown-trigger,
  .chevron,
  .dropdown-item {
    transition: none;
  }
}
</style>

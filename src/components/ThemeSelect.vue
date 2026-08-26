<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
  hint?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    options: SelectOption[]
    placeholder?: string
    label?: string
    disabled?: boolean
    size?: 'sm' | 'md'
    block?: boolean
    align?: 'start' | 'end'
  }>(),
  {
    placeholder: '请选择',
    label: '请选择',
    disabled: false,
    size: 'md',
    block: false,
    align: 'end',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
  open: []
  close: []
}>()

defineOptions({ inheritAttrs: false })

const isOpen = ref(false)
const root = ref<HTMLElement | null>(null)
const activeIndex = ref(props.options.findIndex((o) => o.value === props.modelValue))

const selected = computed(() => props.options.find((o) => o.value === props.modelValue) ?? null)

const selectedLabel = computed(() => selected.value?.label ?? props.placeholder)

function indexOf(value: string) {
  return props.options.findIndex((o) => o.value === value)
}

function moveBy(step: number) {
  const len = props.options.length
  let i = activeIndex.value
  for (let n = 0; n < len; n++) {
    i = (i + step + len) % len
    const option = props.options[i]
    if (option && !option.disabled) {
      activeIndex.value = i
      return
    }
  }
}

function moveToStart() {
  for (let i = 0; i < props.options.length; i++) {
    const option = props.options[i]
    if (option && !option.disabled) {
      activeIndex.value = i
      return
    }
  }
}

function moveToEnd() {
  for (let i = props.options.length - 1; i >= 0; i--) {
    const option = props.options[i]
    if (option && !option.disabled) {
      activeIndex.value = i
      return
    }
  }
}

function commit(index: number) {
  const option = props.options[index]
  if (!option || option.disabled) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
  activeIndex.value = index
  close()
}

function openPanel() {
  isOpen.value = true
  emit('open')
}

function close() {
  if (!isOpen.value) return
  isOpen.value = false
  emit('close')
}

function toggle() {
  if (props.disabled) return
  if (isOpen.value) close()
  else openPanel()
}

function onTriggerKeydown(event: KeyboardEvent) {
  if (props.disabled) return
  const key = event.key
  if (isOpen.value) {
    if (key === 'ArrowDown') {
      event.preventDefault()
      moveBy(1)
    } else if (key === 'ArrowUp') {
      event.preventDefault()
      moveBy(-1)
    } else if (key === 'Home') {
      event.preventDefault()
      moveToStart()
    } else if (key === 'End') {
      event.preventDefault()
      moveToEnd()
    } else if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
      event.preventDefault()
      commit(activeIndex.value)
    } else if (key === 'Escape' || key === 'Tab') {
      close()
    }
    return
  }
  if (
    key === 'ArrowDown' ||
    key === 'ArrowUp' ||
    key === 'Enter' ||
    key === ' ' ||
    key === 'Spacebar' ||
    key === 'Home' ||
    key === 'End'
  ) {
    event.preventDefault()
    activeIndex.value = indexOf(props.modelValue)
    openPanel()
  }
}

function onDocumentClick(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) {
    close()
  }
}

watch(isOpen, (value) => {
  if (value) {
    activeIndex.value = indexOf(props.modelValue)
    requestAnimationFrame(() => {
      root.value
        ?.querySelector<HTMLElement>('[aria-selected="true"]')
        ?.scrollIntoView({ block: 'nearest' })
    })
  }
})

watch(
  () => props.modelValue,
  (value) => {
    activeIndex.value = indexOf(value)
  },
)

watch(
  () => props.options,
  () => {
    activeIndex.value = indexOf(props.modelValue)
  },
)

onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))
</script>

<template>
  <div
    ref="root"
    v-bind="$attrs"
    class="theme-select"
    :class="{
      'is-open': isOpen,
      'is-block': block,
      'is-disabled': disabled,
      [`is-${size}`]: true,
      [`align-${align}`]: true,
    }"
  >
    <button
      class="trigger"
      type="button"
      :aria-haspopup="'listbox'"
      :aria-expanded="isOpen"
      :aria-label="label"
      :aria-disabled="disabled || undefined"
      :disabled="disabled"
      :title="selectedLabel"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <slot name="trigger" :open="isOpen" :selected="selected" :label="selectedLabel">
        <span class="trigger-label">{{ selectedLabel }}</span>
      </slot>

      <slot name="trailing" :open="isOpen" :selected="selected">
        <svg class="chevron" viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M3.5 6 8 10.5 12.5 6"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </slot>
    </button>

    <div v-show="isOpen" class="panel" role="listbox" :aria-label="label || '选项'">
      <button
        v-for="(option, index) in options"
        :key="option.value"
        class="option"
        :class="{ 'is-active': index === activeIndex, 'is-disabled': option.disabled }"
        type="button"
        role="option"
        :aria-selected="option.value === modelValue"
        :aria-disabled="option.disabled || undefined"
        :disabled="option.disabled"
        :title="option.hint ? `${option.label} (${option.hint})` : option.label"
        @click="commit(index)"
        @mouseenter="!option.disabled && (activeIndex = index)"
      >
        <svg class="check" viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M3 8.5 6.5 12 13 4.5"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span class="option-label">{{ option.label }}</span>
        <small v-if="option.hint" class="option-hint">{{ option.hint }}</small>
      </button>
    </div>
  </div>
</template>

<style scoped>
.theme-select {
  position: relative;
  display: inline-flex;
}

.theme-select.is-block {
  display: flex;
  width: 100%;
}

.theme-select.is-block .trigger {
  width: 100%;
}

.trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0) 82%, var(--paper-1));
  color: var(--ink-0);
  font-size: var(--text-sm);
  white-space: nowrap;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.trigger:hover {
  border-color: var(--line-strong);
  background: var(--paper-0);
}

.trigger:focus-visible,
.theme-select.is-open .trigger {
  border-color: var(--accent);
  background: var(--paper-0);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.theme-select.is-md .trigger {
  min-height: var(--control-md);
  padding: 0.45rem 0.9rem 0.45rem 1rem;
}

.theme-select.is-sm .trigger {
  min-height: var(--control-sm);
  padding: 0.25rem 0.65rem 0.25rem 0.8rem;
}

.theme-select.is-disabled .trigger {
  cursor: not-allowed;
  opacity: 0.55;
}

.trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.chevron {
  width: 1rem;
  height: 1rem;
  flex: 0 0 auto;
  color: var(--ink-2);
  transition: transform var(--duration-2) var(--ease-out);
}

.theme-select.is-open .chevron {
  transform: rotate(180deg);
}

.panel {
  position: absolute;
  z-index: 20;
  top: calc(100% + var(--space-2));
  min-width: 100%;
  padding: var(--space-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  box-shadow: var(--shadow-2);
  transform-origin: top right;
  animation: panel-in var(--duration-2) var(--ease-out);
}

.theme-select.align-end .panel {
  right: 0;
}

.theme-select.align-start .panel {
  left: 0;
  right: auto;
}

.option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: 0.5rem 0.9rem;
  border-radius: var(--radius-1);
  background: transparent;
  color: var(--ink-1);
  font-size: var(--text-sm);
  text-align: left;
  white-space: nowrap;
  transition:
    background-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.option:hover,
.option.is-active:not(.is-disabled) {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.option[aria-selected='true'] {
  color: var(--accent-strong);
  font-weight: 600;
}

.option.is-disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.check {
  width: 1rem;
  height: 1rem;
  flex: 0 0 auto;
  opacity: 0;
  transition: opacity var(--duration-1) var(--ease-out);
}

.option[aria-selected='true'] .check {
  opacity: 1;
}

.option-label {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.option-hint {
  flex: 0 0 auto;
  font-size: var(--text-xs);
  color: var(--ink-2);
}

@keyframes panel-in {
  from {
    opacity: 0;
    transform: translateY(-4px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .panel {
    animation: none;
  }
  .chevron {
    transition: none;
  }
}
</style>

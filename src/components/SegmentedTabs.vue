<script setup lang="ts" generic="T extends string | number">
export interface TabItem<T = string | number> {
  key: T
  label: string
  sub?: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: T
    items: (TabItem<T> | string)[]
    size?: 'sm' | 'md' | 'lg'
    disabled?: boolean
    fullWidth?: boolean
    ariaLabel?: string
  }>(),
  {
    size: 'md',
    disabled: false,
    fullWidth: false,
    ariaLabel: 'Tab 导航',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: T]
  change: [value: T]
}>()

function normalizeItem(item: TabItem<T> | string): TabItem<T> {
  if (typeof item === 'string') {
    return { key: item as unknown as T, label: item }
  }
  return item
}

function onSelect(key: T) {
  if (props.disabled || props.modelValue === key) return
  emit('update:modelValue', key)
  emit('change', key)
}

function onKeydown(event: KeyboardEvent, index: number) {
  const normItems = props.items.map(normalizeItem)
  let targetIdx = index
  if (event.key === 'ArrowRight') {
    targetIdx = (index + 1) % normItems.length
  } else if (event.key === 'ArrowLeft') {
    targetIdx = (index - 1 + normItems.length) % normItems.length
  } else if (event.key === 'Home') {
    targetIdx = 0
  } else if (event.key === 'End') {
    targetIdx = normItems.length - 1
  } else {
    return
  }
  event.preventDefault()
  const targetItem = normItems[targetIdx]
  if (targetItem && !targetItem.disabled) {
    onSelect(targetItem.key)
  }
}
</script>

<template>
  <div
    class="segmented-tabs"
    :class="[
      `segmented-tabs--${size}`,
      {
        'is-full-width': fullWidth,
        'is-disabled': disabled,
      },
    ]"
    role="tablist"
    :aria-label="ariaLabel"
  >
    <button
      v-for="(rawItem, idx) in items"
      :key="String(normalizeItem(rawItem).key)"
      type="button"
      role="tab"
      :aria-selected="modelValue === normalizeItem(rawItem).key"
      :tabindex="modelValue === normalizeItem(rawItem).key ? 0 : -1"
      class="segmented-tab"
      :class="{ 'is-active': modelValue === normalizeItem(rawItem).key }"
      :disabled="disabled || normalizeItem(rawItem).disabled"
      @click="onSelect(normalizeItem(rawItem).key)"
      @keydown="(e) => onKeydown(e, idx)"
    >
      <span class="tab-label">{{ normalizeItem(rawItem).label }}</span>
      <span v-if="normalizeItem(rawItem).sub" class="tab-sub">
        {{ normalizeItem(rawItem).sub }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.segmented-tabs {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0.25rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  box-sizing: border-box;
}

.segmented-tabs.is-full-width {
  display: flex;
  width: 100%;
}

.segmented-tabs.is-full-width .segmented-tab {
  flex: 1;
}

.segmented-tabs.is-disabled {
  opacity: 0.6;
  pointer-events: none;
}

.segmented-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1-5);
  border: 0;
  border-radius: var(--radius-1);
  background: transparent;
  color: var(--ink-1);
  cursor: pointer;
  transition:
    background-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out);
  user-select: none;
  white-space: nowrap;
  box-sizing: border-box;
}

.segmented-tab:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-1);
}

.segmented-tab:hover:not(.is-active):not(:disabled) {
  color: var(--ink-0);
  background: color-mix(in oklab, var(--paper-0) 50%, transparent);
}

.segmented-tab.is-active {
  background: var(--paper-0);
  color: var(--accent-strong);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}

.segmented-tab:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* Sizes */
.segmented-tabs--sm .segmented-tab {
  padding: 0.35rem 0.85rem;
  font-size: var(--text-xs);
  line-height: 1.2;
}

.segmented-tabs--md .segmented-tab {
  padding: 0.45rem 1.1rem;
  font-size: var(--text-xs);
  line-height: 1.3;
}

.segmented-tabs--lg .segmented-tab {
  padding: 0.6rem 1.4rem;
  font-size: var(--text-sm);
  line-height: 1.4;
}

.tab-label {
  font-family: var(--font-body);
}

.tab-sub {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  transition: color var(--duration-1) var(--ease-out);
}

.segmented-tab.is-active .tab-sub {
  color: var(--accent);
}
</style>

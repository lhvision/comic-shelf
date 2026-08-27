<script setup lang="ts">
import { computed } from 'vue'
import AppDropdown, { type DropdownOption } from '@/components/AppDropdown.vue'

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
    label: undefined,
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

const dropdownOptions = computed<DropdownOption<string>[]>(() =>
  props.options.map((opt) => ({
    key: opt.value,
    label: opt.label,
    disabled: opt.disabled,
    hint: opt.hint,
  })),
)
</script>

<template>
  <AppDropdown
    v-bind="$attrs"
    :options="dropdownOptions"
    :model-value="modelValue"
    :placeholder="placeholder"
    :label="label"
    :disabled="disabled"
    :size="size"
    :block="block"
    :align="align"
    @update:model-value="(val) => emit('update:modelValue', String(val))"
    @change="(val) => emit('change', String(val))"
  >
    <template v-if="$slots.trigger" #trigger="slotProps">
      <slot
        name="trigger"
        :open="slotProps.open"
        :selected="
          slotProps.selected
            ? {
                value: String(slotProps.selected.key),
                label: slotProps.selected.label,
              }
            : null
        "
        :label="slotProps.label"
      />
    </template>
  </AppDropdown>
</template>

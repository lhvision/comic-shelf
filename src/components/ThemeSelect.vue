<script setup lang="ts">
import { computed } from 'vue'
import AppDropdown from '@/components/AppDropdown.vue'
import type { DropdownOption } from '@/types'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
  hint?: string
}

const modelValue = defineModel<string>({ default: '' })

const props = withDefaults(
  defineProps<{
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
    v-model="modelValue"
    :options="dropdownOptions"
    :placeholder="placeholder"
    :label="label"
    :disabled="disabled"
    :size="size"
    :block="block"
    :align="align"
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

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'soft' | 'danger'
    size?: 'xs' | 'sm' | 'md' | 'lg'
    loading?: boolean
    disabled?: boolean
    type?: 'button' | 'submit' | 'reset'
    block?: boolean
  }>(),
  {
    variant: 'secondary',
    size: 'md',
    loading: false,
    disabled: false,
    type: 'button',
    block: false,
  },
)

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const btnClasses = computed(() => [
  'btn',
  `btn-${props.variant}`,
  `btn-${props.size}`,
  {
    'btn-block': props.block,
    'is-loading': props.loading,
  },
])

function handleClick(event: MouseEvent) {
  if (props.disabled || props.loading) {
    event.preventDefault()
    return
  }
  emit('click', event)
}
</script>

<template>
  <button
    :type="type"
    :class="btnClasses"
    :disabled="disabled || loading"
    :aria-busy="loading ? 'true' : undefined"
    @click="handleClick"
  >
    <span v-if="loading" class="btn-spinner" aria-hidden="true"></span>
    <span v-else-if="$slots.prefix" class="btn-prefix">
      <slot name="prefix"></slot>
    </span>

    <span class="btn-content">
      <slot></slot>
    </span>

    <span v-if="$slots.suffix && !loading" class="btn-suffix">
      <slot name="suffix"></slot>
    </span>
  </button>
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
  animation: btn-spin 0.75s linear infinite;
  flex-shrink: 0;
}

@keyframes btn-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import type { IconSize } from './types'

const props = withDefaults(
  defineProps<{
    size?: IconSize
    strokeWidth?: number | string
    viewBox?: string
  }>(),
  {
    size: 'md',
    strokeWidth: 1.8,
    viewBox: '0 0 24 24',
  },
)

const pixelSize = computed(() => {
  if (typeof props.size === 'number') return `${props.size}px`
  switch (props.size) {
    case 'xs':
      return '12px'
    case 'sm':
      return '14px'
    case 'md':
      return '16px'
    case 'lg':
      return '20px'
    case 'xl':
      return '24px'
    case '2xl':
      return '28px'
    case '3xl':
      return '36px'
    default:
      return /^\d+$/.test(props.size) ? `${props.size}px` : props.size
  }
})
</script>

<template>
  <svg
    class="app-icon"
    :viewBox="viewBox"
    :width="pixelSize"
    :height="pixelSize"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <slot />
  </svg>
</template>

<style scoped>
.app-icon {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}
</style>

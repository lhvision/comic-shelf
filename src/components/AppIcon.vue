<script setup lang="ts">
import { computed } from 'vue'
import { ICON_MAP, type IconName, type IconSize } from '@/components/icons'

export type { IconName, IconSize }

const props = withDefaults(
  defineProps<{
    name: IconName
    size?: IconSize
    strokeWidth?: number | string
  }>(),
  {
    size: 'md',
    strokeWidth: 1.8,
  },
)

const currentComponent = computed(() => ICON_MAP[props.name])
</script>

<template>
  <component
    :is="currentComponent"
    v-if="currentComponent"
    :size="size"
    :stroke-width="strokeWidth"
  />
</template>

<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--close" :size="size" :stroke-width="strokeWidth">
    <path d="M18 6 6 18M6 6l12 12" />
  </BaseIcon>
</template>

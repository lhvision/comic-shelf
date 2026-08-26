<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--arrow-left" :size="size" :stroke-width="strokeWidth">
    <path d="M19 12H5M12 19l-7-7 7-7" />
  </BaseIcon>
</template>

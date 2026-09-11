<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--arrow-down" :size="size" :stroke-width="strokeWidth">
    <path d="M12 5v14M19 12l-7 7-7-7" />
  </BaseIcon>
</template>

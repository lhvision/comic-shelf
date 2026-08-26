<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--more" :size="size" :stroke-width="strokeWidth">
    <circle cx="5" cy="12" r="1.5" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
    <circle cx="19" cy="12" r="1.5" fill="currentColor" stroke="none" />
  </BaseIcon>
</template>

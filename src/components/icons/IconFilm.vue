<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--film" :size="size" :stroke-width="strokeWidth">
    <rect width="20" height="16" x="2" y="4" rx="2" />
    <line x1="8" x2="8" y1="4" y2="20" />
    <line x1="16" x2="16" y1="4" y2="20" />
    <circle cx="5" cy="7" r="0.75" fill="currentColor" />
    <circle cx="5" cy="17" r="0.75" fill="currentColor" />
    <circle cx="12" cy="7" r="0.75" fill="currentColor" />
    <circle cx="12" cy="17" r="0.75" fill="currentColor" />
    <circle cx="19" cy="7" r="0.75" fill="currentColor" />
    <circle cx="19" cy="17" r="0.75" fill="currentColor" />
  </BaseIcon>
</template>

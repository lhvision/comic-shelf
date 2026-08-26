<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--search" :size="size" :stroke-width="strokeWidth">
    <circle cx="11" cy="11" r="7" />
    <path d="m21 21-4.35-4.35" />
  </BaseIcon>
</template>

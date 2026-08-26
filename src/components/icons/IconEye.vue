<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--eye" :size="size" :stroke-width="strokeWidth">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </BaseIcon>
</template>

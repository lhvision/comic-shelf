<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--chevron-up" :size="size" :stroke-width="strokeWidth">
    <path d="m18 15-6-6-6 6" />
  </BaseIcon>
</template>

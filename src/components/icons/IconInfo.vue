<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--info" :size="size" :stroke-width="strokeWidth">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5" />
    <circle cx="12" cy="8" r="0.75" fill="currentColor" stroke="none" />
  </BaseIcon>
</template>

<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--check" :size="size" :stroke-width="strokeWidth">
    <path d="M4.5 12.5 9.5 17.5 19.5 6.5" />
  </BaseIcon>
</template>

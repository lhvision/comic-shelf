<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--play" :size="size" :stroke-width="strokeWidth">
    <polygon points="6 3 20 12 6 21 6 3" />
  </BaseIcon>
</template>

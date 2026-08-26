<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--heart" :size="size" :stroke-width="strokeWidth">
    <path
      d="M12 20.7 4.9 13.5a4.75 4.75 0 0 1 0-6.6 4.6 4.6 0 0 1 6.5 0l.6.6.6-.6a4.6 4.6 0 0 1 6.5 0 4.75 4.75 0 0 1 0 6.6L12 20.7Z"
    />
  </BaseIcon>
</template>

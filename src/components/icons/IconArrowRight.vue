<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--arrow-right" :size="size" :stroke-width="strokeWidth">
    <path d="M5 12h14M12 5l7 7-7 7" />
  </BaseIcon>
</template>

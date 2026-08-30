<script setup lang="ts">
import BaseIcon from '@/components/icons/BaseIcon.vue'
import type { IconSize } from '@/components/icons/types'

defineProps<{
  size?: IconSize
  strokeWidth?: number | string
}>()
</script>

<template>
  <BaseIcon class="app-icon--minus" :size="size" :stroke-width="strokeWidth">
    <path d="M5 12h14" />
  </BaseIcon>
</template>

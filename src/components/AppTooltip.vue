<script setup lang="ts">
import Tooltip from '@/components/Tooltip.vue'
</script>

<template>
  <Tooltip>
    <template #default>
      <slot />
    </template>
    <template v-if="$slots.content" #content>
      <slot name="content" />
    </template>
  </Tooltip>
</template>

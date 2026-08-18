<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import ToastStack from '@/components/ToastStack.vue'
import { useHtmlCanvas } from '@/composables/useHtmlCanvas'

const route = useRoute()
const { supported, publishStatus } = useHtmlCanvas()

onMounted(() => {
  publishStatus(false, supported.value ? 'app:idle' : 'app:unsupported')
})
</script>

<template>
  <div class="app-frame" :data-reader="route.name === 'reader'">
    <AppHeader v-if="route.name !== 'reader'" />
    <main class="app-main">
      <RouterView />
    </main>
    <ToastStack />
  </div>
</template>

<style scoped>
.app-frame {
  min-height: 100dvh;
}

.app-frame[data-reader='true'] .app-main {
  min-height: 100dvh;
}
</style>

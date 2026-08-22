<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import AuthModal from '@/components/AuthModal.vue'
import ToastStack from '@/components/ToastStack.vue'
import AmbientWatermark from '@/components/AmbientWatermark.vue'
import { useAuth } from '@/composables/useAuth'
import { useHtmlCanvas } from '@/composables/useHtmlCanvas'

const route = useRoute()
const { supported, publishStatus } = useHtmlCanvas()
const { checkStatus } = useAuth()

onMounted(async () => {
  publishStatus(false, supported.value ? 'app:idle' : 'app:unsupported')
  await checkStatus()
})
</script>

<template>
  <div class="app-frame" :data-reader="route.name === 'reader'">
    <AmbientWatermark variant="page" />
    <AppHeader v-if="route.name !== 'reader'" />
    <main class="app-main">
      <RouterView />
    </main>
    <ToastStack />
    <AuthModal />
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

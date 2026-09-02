<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import GateView from '@/components/GateView.vue'
import ToastStack from '@/components/ToastStack.vue'
import UpdateBanner from '@/components/UpdateBanner.vue'
import AmbientWatermark from '@/components/AmbientWatermark.vue'
import BackToTop from '@/components/BackToTop.vue'
import { useAuth } from '@/composables/useAuth'
import { useHtmlCanvas } from '@/composables/useHtmlCanvas'
import { useBrandIcon } from '@/composables/useBrandIcon'

const route = useRoute()
const { supported, publishStatus } = useHtmlCanvas()
const { authRequired, authenticated, checkStatus } = useAuth()
const { syncFavicon } = useBrandIcon()

onMounted(async () => {
  syncFavicon()
  publishStatus(false, supported.value ? 'app:idle' : 'app:unsupported')
  await checkStatus()
})
</script>

<template>
  <div
    v-if="!authRequired || authenticated"
    class="app-frame"
    :data-reader="route.name === 'reader'"
  >
    <AmbientWatermark variant="page" />
    <AppHeader v-if="route.name !== 'reader'" />
    <main class="app-main">
      <RouterView />
    </main>
    <BackToTop v-if="route.name !== 'reader'" />
    <ToastStack />
    <UpdateBanner />
  </div>

  <GateView v-else />
</template>

<style scoped>
.app-frame {
  min-height: 100dvh;
}

.app-frame[data-reader='true'] .app-main {
  min-height: 100dvh;
}
</style>

import { computed, ref } from 'vue'
import { createGlobalState, useEventListener } from '@vueuse/core'

export interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[]
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
    platform: string
  }>
  prompt(): Promise<void>
}

export const usePwaInstall = createGlobalState(() => {
  const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)
  const isInstalled = ref(false)

  // 探测是否处于独立应用模式（PWA Standalone 视口）
  const isStandalone = computed(() => {
    if (typeof window === 'undefined') return false
    const isStandaloneDisplay =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(display-mode: standalone)').matches
    const isIosStandalone =
      typeof navigator !== 'undefined' &&
      (navigator as unknown as { standalone?: boolean }).standalone === true
    return !!(isStandaloneDisplay || isIosStandalone)
  })

  const canInstall = computed(
    () => !isStandalone.value && !isInstalled.value && !!deferredPrompt.value,
  )

  if (typeof window !== 'undefined') {
    useEventListener(window, 'beforeinstallprompt', (e: Event) => {
      e.preventDefault()
      deferredPrompt.value = e as BeforeInstallPromptEvent
    })

    useEventListener(window, 'appinstalled', () => {
      isInstalled.value = true
      deferredPrompt.value = null
    })
  }

  async function installApp(): Promise<boolean> {
    if (!deferredPrompt.value) return false
    try {
      await deferredPrompt.value.prompt()
      const choice = await deferredPrompt.value.userChoice
      deferredPrompt.value = null
      if (choice.outcome === 'accepted') {
        isInstalled.value = true
        return true
      }
      return false
    } catch {
      deferredPrompt.value = null
      return false
    }
  }

  return {
    canInstall,
    isStandalone,
    installApp,
  }
})

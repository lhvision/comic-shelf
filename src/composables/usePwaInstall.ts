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

  // 探测当前是否处于 iOS / iPadOS 环境
  const isIos = computed(() => {
    if (typeof navigator === 'undefined') return false
    const ua = navigator.userAgent || ''
    const isAppleMobile = /iPhone|iPad|iPod/i.test(ua)
    const isIpadOs = navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
    return isAppleMobile || isIpadOs
  })

  // iOS Safari 因 WebKit 不支持 beforeinstallprompt，当处于非独立视口时展示添加到主屏幕引导
  const showIosGuide = computed(() => isIos.value && !isStandalone.value)

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
    /** Chromium / Android 设备是否可弹出原生安装面板 */
    canInstall,
    /** 当前是否已在 Standalone 独立视口运行 */
    isStandalone,
    /** 当前运行设备是否为 iOS / iPadOS */
    isIos,
    /** 是否向 iOS 用户展示原生「添加到主屏幕」指引胶囊 */
    showIosGuide,
    /** 触发应用安装流 */
    installApp,
  }
})

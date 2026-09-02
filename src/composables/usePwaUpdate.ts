import { computed, ref, watch } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import { createGlobalState, useDocumentVisibility, useIntervalFn, useNetwork } from '@vueuse/core'

/**
 * 适配不同宿主环境（浏览器 / jsdom 单测 / SSR）的安全页面重载执行器
 */
function triggerWindowReload(): void {
  if (typeof window === 'undefined') return
  try {
    window.location.reload()
  } catch {
    // jsdom 或部分轻量无头单测环境下 location.reload 可能未完整实现，静默容错
  }
}

/**
 * PWA Prompt 模式生命周期状态机
 * 托管 Service Worker 更新发现、离线就绪、页面唤醒回源探测与平滑装订
 */
export const usePwaUpdate = createGlobalState(() => {
  const needRefresh = ref(false)
  const offlineReady = ref(false)
  const isUpdating = ref(false)
  const hasDismissedPrompt = ref(false)
  const registration = ref<ServiceWorkerRegistration | null>(null)

  const visibility = useDocumentVisibility()
  const { isOnline } = useNetwork()

  let updateSWFn: ((reloadPage?: boolean) => Promise<void>) | null = null

  if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
    updateSWFn = registerSW({
      immediate: true,
      onNeedRefresh() {
        needRefresh.value = true
        // 若之前 dismiss 过，新一轮更新再次浮现
        hasDismissedPrompt.value = false
      },
      onOfflineReady() {
        offlineReady.value = true
      },
      onRegisteredSW(_swUrl, r) {
        if (r) {
          registration.value = r
        }
      },
    })

    // 1. 当页面从后台唤醒重新可见时，静默探测一次 Service Worker 变更 (0 业务接口请求)
    watch(visibility, (current) => {
      if (current === 'visible' && isOnline.value && registration.value) {
        void checkForUpdate()
      }
    })

    // 2. 当网络从离线切回在线时，静默触发一次自愈更新检查
    watch(isOnline, (online) => {
      if (online && registration.value) {
        void checkForUpdate()
      }
    })

    // 3. 周期性静默探测 Service Worker 版本变更（每 30 分钟一次）
    useIntervalFn(
      () => {
        if (isOnline.value && registration.value) {
          void checkForUpdate()
        }
      },
      30 * 60 * 1000,
    )
  }

  /**
   * 手动或事件触发探测 Service Worker 更新
   */
  async function checkForUpdate(): Promise<void> {
    if (!registration.value || registration.value.installing) return
    try {
      await registration.value.update()
    } catch {
      // 弱网或离线环境下静默忽略网络异常
    }
  }

  /**
   * 读者确认立即应用新版本（跳过等待并平滑刷新）
   */
  async function applyUpdate(): Promise<void> {
    if (isUpdating.value) return
    isUpdating.value = true

    // 设置安全熔断兜底：若 ServiceWorker 未能在预期时间内触发 controllerchange，强制执行刷新，彻底防止无限转圈
    let reloaded = false
    const safeReload = () => {
      if (reloaded) return
      reloaded = true
      triggerWindowReload()
    }

    const fallbackTimer = setTimeout(safeReload, 1200)

    try {
      if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
        navigator.serviceWorker.addEventListener(
          'controllerchange',
          () => {
            clearTimeout(fallbackTimer)
            safeReload()
          },
          { once: true },
        )

        // 若存在等待中的新 ServiceWorker，直接发送跳过等待消息
        if (registration.value?.waiting) {
          registration.value.waiting.postMessage({ type: 'SKIP_WAITING' })
        }
      }

      if (updateSWFn) {
        await updateSWFn(true)
      } else {
        clearTimeout(fallbackTimer)
        safeReload()
      }
    } catch {
      clearTimeout(fallbackTimer)
      safeReload()
    }
  }

  /**
   * 读者选择稍后装订（收起悬浮胶囊，保留顶栏角标）
   */
  function dismissPrompt(): void {
    hasDismissedPrompt.value = true
  }

  // 是否展示悬浮装订提示横幅（有新版本且用户未点稍后）
  const showPrompt = computed(() => needRefresh.value && !hasDismissedPrompt.value)

  return {
    needRefresh,
    offlineReady,
    isUpdating,
    hasDismissedPrompt,
    showPrompt,
    registration,
    checkForUpdate,
    applyUpdate,
    dismissPrompt,
  }
})

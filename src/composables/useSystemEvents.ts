import { computed, ref, watch } from 'vue'
import { createGlobalState, useDocumentVisibility, useIdle, useNetwork } from '@vueuse/core'
import { clearApiDetailCache } from '@/api/client'
import { usePwaUpdate } from '@/composables/usePwaUpdate'
import router from '@/router'
import { useLibraryStore } from '@/stores/library'

export const MAX_SSE_RETRY_ATTEMPTS = 10
export const DEFAULT_IDLE_TIMEOUT_MS = 10 * 60 * 1000 // 10 minutes

/**
 * 纸间全站智能按需单向系统事件流（SSE）
 *
 * 核心特性：
 * 1. 0 轮询开销，0% CPU 占用，具备指数平滑退避自动重连；
 * 2. 沉浸阅读自动避让：进入阅读器路由（/read/...）时主动断开长连接，
 *    释放内网 HTTP/1.1 单域名 6 连接槽位与网络带宽，退出时自动恢复；
 * 3. 视口与闲置深度休眠：离开视口（hidden）或挂机闲置（>= 10min）时主动切断，
 *    彻底消除后台无意义的 keepalive 心跳唤醒与 DevTools 悬挂长连接；
 * 4. 唤醒静默对齐：从休眠或阅读器唤醒重连后，自动对齐书架数据与 PWA 构建版本，
 *    消除断开期间的事件盲区。
 */
export const useSystemEvents = createGlobalState(() => {
  const isConnected = ref(false)
  const isSleeping = ref(false)

  // 是否由应用显式激活（由 registerPwa 或视图调用 connect() 时激活）
  const isEnabled = ref(false)

  const visibility = useDocumentVisibility()
  const { isOnline } = useNetwork()
  const { idle } = useIdle(DEFAULT_IDLE_TIMEOUT_MS)
  const { checkForUpdate } = usePwaUpdate()

  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let retryAttempts = 0
  let hasConnectedOnce = false
  let lastReconcileTime = 0
  const RECONCILE_THROTTLE_MS = 3000

  // 判定当前是否处于阅读器沉浸路由
  const isReaderRoute = computed(() => {
    const route = router.currentRoute.value
    return Boolean(route?.name === 'reader' || route?.path?.includes('/read/'))
  })

  // 动态派生当前是否应该保持 SSE 物理连接
  const shouldBeConnected = computed(() => {
    return (
      isEnabled.value &&
      isOnline.value &&
      visibility.value === 'visible' &&
      !idle.value &&
      !isReaderRoute.value
    )
  })

  /**
   * 休眠或重连建立成功后，执行静默对齐补齐期间可能遗漏的事件（3s 防抖节流）
   */
  async function reconcileState(): Promise<void> {
    const now = Date.now()
    if (now - lastReconcileTime < RECONCILE_THROTTLE_MS) {
      return
    }
    lastReconcileTime = now

    try {
      clearApiDetailCache()
      const libraryStore = useLibraryStore()
      await libraryStore.load(true)
      await checkForUpdate()
    } catch {
      // 对齐失败静默降级
    }
  }

  function startEventSource(): void {
    if (typeof window === 'undefined' || typeof EventSource === 'undefined') return
    if (eventSource) return

    try {
      eventSource = new EventSource('/api/events/stream', {
        withCredentials: true,
      })

      eventSource.onopen = () => {
        isConnected.value = true
        isSleeping.value = false
        retryAttempts = 0
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
          reconnectTimer = null
        }
        // 如果此前已成功连过且处于重新唤醒阶段，执行静默状态补齐
        if (hasConnectedOnce) {
          void reconcileState()
        }
        hasConnectedOnce = true
      }

      eventSource.addEventListener('system_version', () => {
        void checkForUpdate()
      })

      eventSource.addEventListener('library_changed', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as { source?: string; source_id?: string }
          if (data?.source && data?.source_id) {
            clearApiDetailCache(data.source, data.source_id)
          } else {
            clearApiDetailCache()
          }
          const libraryStore = useLibraryStore()
          void libraryStore.load(true)
        } catch {
          // 静默容错
        }
      })

      eventSource.onerror = () => {
        isConnected.value = false
        if (eventSource) {
          eventSource.close()
          eventSource = null
        }
        // 指数平滑退避自动重连（仅在仍应连接时重试）
        if (shouldBeConnected.value && !reconnectTimer && retryAttempts < MAX_SSE_RETRY_ATTEMPTS) {
          const delay = Math.min(30000, 2000 * Math.pow(1.5, retryAttempts) + Math.random() * 1000)
          retryAttempts += 1
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null
            if (shouldBeConnected.value) {
              startEventSource()
            }
          }, delay)
        }
      }
    } catch {
      isConnected.value = false
    }
  }

  function teardownEventSource(sleeping = false): void {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isConnected.value = false
    isSleeping.value = sleeping
  }

  /**
   * 显式开启或唤醒系统事件流
   */
  function connect(): void {
    isEnabled.value = true
    if (shouldBeConnected.value) {
      startEventSource()
    } else {
      isSleeping.value = true
    }
  }

  /**
   * 显式切断系统事件流
   */
  function disconnect(): void {
    isEnabled.value = false
    retryAttempts = 0
    teardownEventSource(false)
  }

  // 监听动态连接意图：在条件变更时自适应连接或优雅挂起
  watch(
    shouldBeConnected,
    (shouldConnect) => {
      if (shouldConnect) {
        retryAttempts = 0
        startEventSource()
      } else if (isEnabled.value) {
        // 仍处于全局启用态，但进入了休眠触发条件（阅读器/隐藏/闲置/离线）
        teardownEventSource(true)
      } else {
        teardownEventSource(false)
      }
    },
    { immediate: false },
  )

  return {
    isConnected,
    isSleeping,
    shouldBeConnected,
    isReaderRoute,
    connect,
    disconnect,
    reconcileState,
  }
})

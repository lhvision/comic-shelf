import { computed, ref, watch } from 'vue'
import {
  createGlobalState,
  useBroadcastChannel,
  useDocumentVisibility,
  useNetwork,
} from '@vueuse/core'
import { clearApiDetailCache } from '@/api/client'
import { usePwaUpdate } from '@/composables/usePwaUpdate'
import router from '@/router'
import { useLibraryStore } from '@/stores/library'

export const MAX_SSE_RETRY_ATTEMPTS = 10
export const TASK_TEARDOWN_COOLDOWN_MS = 5000 // 5 seconds graceful teardown cooldown
export const BROADCAST_CHANNEL_NAME = 'paper-room'

export interface LibraryChangedEvent {
  action?: string
  source?: string
  source_id?: string
  chapter_id?: string
  timestamp?: number
}

/**
 * 纸间任务驱动型单向系统事件流（Task-Driven SSE）与本地多标签页广播
 *
 * 核心架构契约：
 * 1. 任务驱动按需拉起：平时全站常态保持断开，0 挂起、0 pending 请求；仅在有活跃异步任务（如导入、缓存）时动态建立连接；
 * 2. 平滑防抖注销冷却：全部活跃任务结束后，延迟 5 秒（TASK_TEARDOWN_COOLDOWN_MS）再切断，避免连环任务频繁反复握手；
 * 3. 沉浸阅读自动避让：进入阅读器（/read/...）自动断开，倾斜内网并发带宽，退出时自愈对齐；
 * 4. 视口与离线按需休眠：离开视口（hidden）或离线主动切断，任务完毕平滑冷却断开，彻底杜绝挂机误掐断长耗时下载；
 * 5. 唤醒静默对齐：从休眠或阅读器唤醒重连后，自动执行 reconcileState() 补齐事件盲区；
 * 6. 本地多标签页零网络同步：基于 VueUse useBroadcastChannel（'paper-room'），单设备内跨 Tab 变动 0 流量、0 延迟直达。
 */
export const useSystemEvents = createGlobalState(() => {
  const isConnected = ref(false)
  const isSleeping = ref(false)
  const lastLibraryEvent = ref<LibraryChangedEvent | null>(null)

  // 活跃异步任务集合（以任务唯一标识存储，如 'import:jm/123', 'cache:jm/123'）
  const activeTasks = ref<Set<string>>(new Set())
  // 5 秒平滑防抖冷却状态
  const isCoolingDown = ref(false)
  let teardownCooldownTimer: ReturnType<typeof setTimeout> | null = null

  // 是否由应用显式激活（用于单测或显式常开场景）
  const isExplicitlyConnected = ref(false)

  const visibility = useDocumentVisibility()
  const { isOnline } = useNetwork()
  const { checkForUpdate } = usePwaUpdate()

  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let retryAttempts = 0
  let hasConnectedOnce = false
  let lastReconcileTime = 0
  const RECONCILE_THROTTLE_MS = 3000

  // 本地多标签页零网络通信管道（同源标签页直连）
  const {
    data: localBroadcastData,
    post: postLocalBroadcast,
    isSupported: isBroadcastSupported,
  } = useBroadcastChannel<LibraryChangedEvent, LibraryChangedEvent>({
    name: BROADCAST_CHANNEL_NAME,
  })

  // 判定当前是否处于阅读器沉浸路由
  const isReaderRoute = computed(() => {
    const route = router.currentRoute.value
    return Boolean(route?.name === 'reader' || route?.path?.includes('/read/'))
  })

  // 活跃任务数与判定
  const activeTaskCount = computed(() => activeTasks.value.size)
  const hasActiveTasks = computed(() => activeTasks.value.size > 0)

  // 动态派生当前是否应该保持 SSE 物理连接
  const shouldBeConnected = computed(() => {
    const hasActiveIntent =
      hasActiveTasks.value || isCoolingDown.value || isExplicitlyConnected.value
    return (
      hasActiveIntent && isOnline.value && visibility.value === 'visible' && !isReaderRoute.value
    )
  })

  /**
   * 清除平滑防抖冷却定时器
   */
  function clearTeardownCooldown(): void {
    if (teardownCooldownTimer) {
      clearTimeout(teardownCooldownTimer)
      teardownCooldownTimer = null
    }
    isCoolingDown.value = false
  }

  /**
   * 登记一项活跃后台任务，即刻动态拉起或维持 SSE 长连接通道
   * @param taskId 任务唯一标识（如 'import:jm/12345'）
   */
  function beginTask(taskId: string): void {
    clearTeardownCooldown()
    if (!activeTasks.value.has(taskId)) {
      const next = new Set(activeTasks.value)
      next.add(taskId)
      activeTasks.value = next
    }
  }

  /**
   * 注销一项后台任务。当所有活跃任务归零后，启动 5 秒防抖冷却，超时自动断开长连接
   * @param taskId 任务唯一标识
   */
  function endTask(taskId: string): void {
    if (activeTasks.value.has(taskId)) {
      const next = new Set(activeTasks.value)
      next.delete(taskId)
      activeTasks.value = next
    }
    if (activeTasks.value.size === 0 && !isExplicitlyConnected.value && isConnected.value) {
      clearTeardownCooldown()
      isCoolingDown.value = true
      teardownCooldownTimer = setTimeout(() => {
        teardownCooldownTimer = null
        isCoolingDown.value = false
      }, TASK_TEARDOWN_COOLDOWN_MS)
    }
  }

  /**
   * 统一消费书库变更事件（供 SSE 远程广播与本地 BroadcastChannel 共同复用）
   */
  function handleLibraryChanged(data: LibraryChangedEvent): void {
    if (!data) return
    try {
      if (data.source && data.source_id) {
        clearApiDetailCache(data.source, data.source_id)
      } else {
        clearApiDetailCache()
      }
      lastLibraryEvent.value = data
      const libraryStore = useLibraryStore()
      void libraryStore.load(true)

      // 任务完成事件自动对齐并解除对应任务
      if (data.action === 'cache_complete' && data.source && data.source_id) {
        endTask(`cache:${data.source}/${data.source_id}`)
        endTask(`import:${data.source}/${data.source_id}`)
      }
      if (
        data.action === 'chapter_cache_complete' &&
        data.source &&
        data.source_id &&
        data.chapter_id
      ) {
        endTask(`chapter:${data.source}/${data.source_id}/${data.chapter_id}`)
      }
    } catch {
      // 静默容错
    }
  }

  // 监听来自同源其他标签页的本地广播，0 毫秒零流量同步
  watch(localBroadcastData, (incoming) => {
    if (incoming) {
      handleLibraryChanged(incoming)
    }
  })

  /**
   * 向同源其他标签页广播本地书库变动（不占用后端长连接与网络带宽）
   * @param event 变更事件体
   */
  function broadcastLocalChange(event: LibraryChangedEvent): void {
    if (isBroadcastSupported.value) {
      try {
        postLocalBroadcast(event)
      } catch {
        // 跨上下文通信失败静默降级
      }
    }
  }

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
      lastLibraryEvent.value = { action: 'reconcile', timestamp: now }
      const libraryStore = useLibraryStore()
      await libraryStore.load(true)
      await checkForUpdate()
    } catch {
      // 对齐失败静默降级
    }
  }

  // 视口激活回源校验：当从其他应用/标签页切回纸间且处于活跃前台时，静默对齐书架与版本（受 3s 节流保护）
  watch(visibility, (state) => {
    if (state === 'visible' && isOnline.value) {
      void reconcileState()
    }
  })

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
          const data = JSON.parse(e.data) as LibraryChangedEvent
          handleLibraryChanged(data)
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
    if (isExplicitlyConnected.value) return
    isExplicitlyConnected.value = true
    clearTeardownCooldown()
    if (!shouldBeConnected.value) {
      isSleeping.value = true
    }
  }

  /**
   * 显式切断系统事件流
   */
  function disconnect(): void {
    isExplicitlyConnected.value = false
    clearTeardownCooldown()
    activeTasks.value = new Set()
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
      } else if (hasActiveTasks.value || isExplicitlyConnected.value) {
        // 仍处于活跃意图，但进入了避让条件（阅读器/隐藏/闲置/离线）
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
    activeTaskCount,
    hasActiveTasks,
    isCoolingDown,
    lastLibraryEvent,
    beginTask,
    endTask,
    broadcastLocalChange,
    connect,
    disconnect,
    reconcileState,
  }
})

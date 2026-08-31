import { ref, watch } from 'vue'
import { createGlobalState, useNetwork } from '@vueuse/core'
import { usePwaUpdate } from '@/composables/usePwaUpdate'
import { useLibraryStore } from '@/stores/library'

export interface SystemVersionEvent {
  version?: string
  hash?: string
  timestamp?: number
}

export interface LibraryChangeEvent {
  action?: string
  source?: string
  source_id?: string
  timestamp?: number
}

export interface AiTaskProgressEvent {
  task_id: string
  progress: number
  status: 'running' | 'completed' | 'failed'
  message?: string
}

/**
 * 纸间全站单向系统事件流（SSE）
 * 承载版本更新广播、藏书后台变动与未来 AI 任务流式状态
 * 0 轮询开销，0% CPU 占用，自动断线自愈
 */
export const useSystemEvents = createGlobalState(() => {
  const isConnected = ref(false)
  const lastPing = ref<number | null>(null)
  const lastVersionEvent = ref<SystemVersionEvent | null>(null)
  const lastLibraryEvent = ref<LibraryChangeEvent | null>(null)
  const aiTasks = ref<Record<string, AiTaskProgressEvent>>({})

  const { isOnline } = useNetwork()
  const { checkForUpdate } = usePwaUpdate()

  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let retryAttempts = 0

  function connect(): void {
    if (typeof window === 'undefined' || typeof EventSource === 'undefined') return
    if (eventSource) return

    try {
      eventSource = new EventSource('/api/events/stream', {
        withCredentials: true,
      })

      eventSource.onopen = () => {
        isConnected.value = true
        retryAttempts = 0
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
          reconnectTimer = null
        }
      }

      eventSource.addEventListener('ping', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          lastPing.value = data.timestamp || Date.now()
        } catch {
          lastPing.value = Date.now()
        }
      })

      eventSource.addEventListener('system_version', (e: MessageEvent) => {
        try {
          const data: SystemVersionEvent = JSON.parse(e.data)
          lastVersionEvent.value = data
          // 收到新版本发布广播，立即触发 Service Worker 字节比对
          void checkForUpdate()
        } catch {
          void checkForUpdate()
        }
      })

      eventSource.addEventListener('library_changed', (e: MessageEvent) => {
        try {
          const data: LibraryChangeEvent = JSON.parse(e.data)
          lastLibraryEvent.value = data
          const libraryStore = useLibraryStore()
          void libraryStore.load(true)
        } catch {
          // 静默解析
        }
      })

      eventSource.addEventListener('ai_task_progress', (e: MessageEvent) => {
        try {
          const data: AiTaskProgressEvent = JSON.parse(e.data)
          if (data.task_id) {
            aiTasks.value[data.task_id] = data
          }
        } catch {
          // 静默忽略畸形消息
        }
      })

      eventSource.onerror = () => {
        isConnected.value = false
        if (eventSource) {
          eventSource.close()
          eventSource = null
        }
        // 指数平滑退避自动重连（从 2s 起步，上限 30s，附加抖动）
        if (isOnline.value && !reconnectTimer) {
          const delay = Math.min(30000, 2000 * Math.pow(1.5, retryAttempts) + Math.random() * 1000)
          retryAttempts += 1
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null
            connect()
          }, delay)
        }
      }
    } catch {
      isConnected.value = false
    }
  }

  function disconnect(): void {
    retryAttempts = 0
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isConnected.value = false
  }

  // 监听网络连接变化：网络恢复时重新连接
  watch(isOnline, (online) => {
    if (online && !isConnected.value && !eventSource) {
      connect()
    } else if (!online) {
      disconnect()
    }
  })

  return {
    isConnected,
    lastPing,
    lastVersionEvent,
    lastLibraryEvent,
    aiTasks,
    connect,
    disconnect,
  }
})

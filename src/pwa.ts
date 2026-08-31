import { usePwaUpdate } from '@/composables/usePwaUpdate'
import { useSystemEvents } from '@/composables/useSystemEvents'

/**
 * 初始化 PWA 生命周期托管与 SSE 系统事件流
 * 遵循 W3C Service Worker 规范与零轮询优雅通信架构
 */
export function registerPwa(): void {
  if (typeof window === 'undefined') {
    return
  }

  // 1. 初始化 PWA 更新状态机与视口探测
  usePwaUpdate()

  // 2. 建立单向系统事件长连接（广播版本更新与 AI 任务）
  const { connect } = useSystemEvents()
  connect()
}

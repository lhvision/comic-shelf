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

  // 2. 初始化任务驱动型系统事件流与多标签页广播（常态保持静默，有任务时按需拉起）
  useSystemEvents()
}

/**
 * @file useIdlePrefetch.ts
 * @description 闲时意图预热钩子：在组件挂载且主线程空闲时静默预加载异步模块（如阅读器视图），
 * 避免未来视图 Chunk 混入当前页面的初始关键请求链（Critical Request Chains）。
 */

import { onBeforeUnmount, onMounted } from 'vue'

export interface IdlePrefetchOptions {
  /**
   * requestIdleCallback 期望的最大延迟上限（毫秒），默认 3000ms
   */
  timeout?: number
  /**
   * 当环境不支持 requestIdleCallback 时的回退延迟（毫秒），默认 2000ms
   */
  fallbackDelay?: number
}

/**
 * 调度闲时预热异步模块
 *
 * @param loader 异步模块导入函数，如 `() => import('@/views/ReaderView.vue')`
 * @param options 调度配置项（超时上限与降级延时）
 */
export function useIdlePrefetch(
  loader: () => Promise<unknown>,
  options: IdlePrefetchOptions = {},
): void {
  const { timeout = 3000, fallbackDelay = 2000 } = options
  let idleHandle: number | null = null
  let timerHandle: ReturnType<typeof setTimeout> | null = null

  onMounted(() => {
    if (typeof window === 'undefined') return

    if ('requestIdleCallback' in window) {
      idleHandle = window.requestIdleCallback(
        () => {
          idleHandle = null
          void loader().catch(() => {})
        },
        { timeout },
      )
    } else {
      timerHandle = setTimeout(() => {
        timerHandle = null
        void loader().catch(() => {})
      }, fallbackDelay)
    }
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') return
    if (idleHandle !== null && 'cancelIdleCallback' in window) {
      window.cancelIdleCallback(idleHandle)
      idleHandle = null
    }
    if (timerHandle !== null) {
      clearTimeout(timerHandle)
      timerHandle = null
    }
  })
}

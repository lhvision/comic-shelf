/**
 * @file testUtils.ts
 * @description 纸间前端单测通用测试工具库，遵循 Vue 3 Testing Best Practices 与 Vitest 规范。
 * 提供 Composable 宿主上下文包装器 (withSetup)、Pinia 测试初始化与微任务/异步刷新助手。
 */

import { createApp, type App, type InjectionKey } from 'vue'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

export interface WithSetupOptions {
  /** 自定义 Pinia 实例（若未提供且需状态管理，可自动创建或挂载） */
  pinia?: Pinia
  /** 依赖注入提供项 (Provide/Inject) */
  providers?: Array<[string | InjectionKey<unknown>, unknown]>
}

/**
 * 为依赖生命周期钩子 (onMounted, onUnmounted) 或依赖注入 (inject) 的复杂 Composable 提供宿主上下文。
 *
 * @param composable 需要测试的 Composable 函数
 * @param options 可选配置（自定义 Pinia、依赖注入 Provide 表等）
 * @returns [Composable 返回值, Vue App 实例, 挂载容器元素]
 *
 * @example
 * ```ts
 * const [result, app] = withSetup(() => useFetch('/api/data'))
 * await flushPromises()
 * expect(result.data.value).toBeDefined()
 * app.unmount()
 * ```
 */
export function withSetup<T>(
  composable: () => T,
  options: WithSetupOptions = {},
): [result: T, app: App, container: HTMLDivElement] {
  let result!: T

  const app = createApp({
    setup() {
      result = composable()
      // 返回空渲染函数抑制无模板警告
      return () => null
    },
  })

  // 挂载 Pinia
  const pinia = options.pinia || createPinia()
  app.use(pinia)
  setActivePinia(pinia)

  // 挂载 Provide 依赖
  if (options.providers) {
    for (const [key, value] of options.providers) {
      app.provide(key, value)
    }
  }

  const container = document.createElement('div')
  app.mount(container)

  return [result, app, container]
}

/**
 * 快速刷新所有已排队的 Promise 微任务与 DOM 更新队列。
 */
export async function flushAsync(): Promise<void> {
  await flushPromises()
}

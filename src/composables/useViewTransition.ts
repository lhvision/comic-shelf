/**
 * 纸间 · View Transitions API 统一门面。
 *
 * 遵循张鑫旭文章与 W3C / MDN 规范，支持：
 * 1. 局部 Element-Scoped View Transition (Element.prototype.startViewTransition)
 * 2. 全局 Document View Transition (document.startViewTransition + types)
 * 3. 优雅降级（不支持、用户开启 prefers-reduced-motion 或被后续过渡抢占中断时安全处理 AbortError）
 */
import { withResolvers, promiseTry } from '@/utils/promise'

export interface ViewTransitionOptions {
  /** 目标容器元素（用于 element-scoped view transition） */
  element?: HTMLElement | null
  /** 目标容器元素（兼容别名） */
  scope?: HTMLElement | null
  /** 视图过渡类型（配合 :active-view-transition-type()） */
  types?: string[]
}

interface GenericViewTransition {
  ready?: Promise<void>
  finished?: Promise<void>
  updateCallbackDone?: Promise<void>
}

export function useViewTransition() {
  const isSupported = typeof document !== 'undefined' && 'startViewTransition' in document

  const prefersReducedMotion = () =>
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  /**
   * 执行带有 View Transition 的状态变更。
   * 采用 Promise.withResolvers() 解耦结果承诺与快照周期，
   * 结合 Promise.try() 统一捕获同步与异步状态变更，杜绝 mutable 变量逃逸与 non-null 断言。
   */
  async function withViewTransition<T>(
    callback: () => T | Promise<T>,
    options?: ViewTransitionOptions,
  ): Promise<T> {
    if (prefersReducedMotion()) {
      return await promiseTry(callback)
    }

    // 若显式指定了 element 或 scope 作用域（如单图加载、独立按钮状态）
    const targetEl = options?.element ?? options?.scope
    if (targetEl !== undefined) {
      if (
        targetEl &&
        typeof (targetEl as unknown as { startViewTransition?: unknown }).startViewTransition ===
          'function'
      ) {
        try {
          const { promise, resolve, reject } = withResolvers<T>()
          let executed = false
          const transition = (
            targetEl as unknown as {
              startViewTransition: (cb: () => Promise<void>) => GenericViewTransition
            }
          ).startViewTransition(async () => {
            executed = true
            const task = promiseTry(callback)
            task.then(resolve, reject)
            await task.catch(() => {})
          })
          const ensureExecuted = () => {
            if (!executed) {
              executed = true
              promiseTry(callback).then(resolve, reject)
            }
          }
          transition?.ready?.catch(() => {})
          transition?.updateCallbackDone?.catch(ensureExecuted)
          await transition?.finished?.catch(ensureExecuted)
          return await promise
        } catch {
          // 局部失败时直接回退执行，绝不激进回退到全局全屏快照
        }
      }
      // 不支持局部过渡时直接执行，避免多图并发加载时触发频繁全屏快照
      return await promiseTry(callback)
    }

    // 全局 document.startViewTransition
    if (isSupported) {
      try {
        if (options?.types && options.types.length > 0) {
          const { promise, resolve, reject } = withResolvers<T>()
          let executed = false
          const doc = document as unknown as {
            startViewTransition: (opt: {
              update: () => Promise<void>
              types: string[]
            }) => GenericViewTransition
          }
          const transition = doc.startViewTransition({
            update: async () => {
              executed = true
              const task = promiseTry(callback)
              task.then(resolve, reject)
              await task.catch(() => {})
            },
            types: options.types,
          })
          const ensureExecuted = () => {
            if (!executed) {
              executed = true
              promiseTry(callback).then(resolve, reject)
            }
          }
          transition?.ready?.catch(() => {})
          transition?.updateCallbackDone?.catch(ensureExecuted)
          await transition?.finished?.catch(ensureExecuted)
          return await promise
        }
      } catch {
        // 部分浏览器不支持 { update, types } 传参对象，降级为普通回调参数
      }

      try {
        const { promise, resolve, reject } = withResolvers<T>()
        let executed = false
        const transition = (
          document as unknown as {
            startViewTransition: (cb: () => Promise<void>) => GenericViewTransition
          }
        ).startViewTransition(async () => {
          executed = true
          const task = promiseTry(callback)
          task.then(resolve, reject)
          await task.catch(() => {})
        })
        const ensureExecuted = () => {
          if (!executed) {
            executed = true
            promiseTry(callback).then(resolve, reject)
          }
        }
        transition?.ready?.catch(() => {})
        transition?.updateCallbackDone?.catch(ensureExecuted)
        await transition?.finished?.catch(ensureExecuted)
        return await promise
      } catch {
        // Fall through
      }
    }

    // 最终降级：直接执行
    return await promiseTry(callback)
  }

  return {
    isSupported,
    withViewTransition,
  }
}

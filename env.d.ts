/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

declare module '*.css'

declare module 'virtual:illustrations' {
  export const illustrations: string[]
}

// ECMAScript 2024 / 2025 Promise extensions
interface PromiseWithResolvers<T> {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
  reject: (reason?: unknown) => void
}

interface PromiseConstructor {
  /**
   * Creates a new Promise and returns it alongside its resolve and reject functions.
   * Baseline 2024 (Chrome 119+, Firefox 121+, Safari 17.4+, Node.js 22+)
   */
  withResolvers<T>(): PromiseWithResolvers<T>

  /**
   * Takes a callback of any kind (returns or throws, synchronously or asynchronously)
   * and wraps its execution in a Promise.
   * Baseline 2025 (Chrome 128+, Firefox 134+, Safari 18.2+, Node.js 23+)
   */
  try<T, A extends unknown[]>(
    fn: (...args: A) => T | PromiseLike<T>,
    ...args: A
  ): Promise<Awaited<T>>
}

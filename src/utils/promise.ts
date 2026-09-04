/**
 * @file promise.ts
 * @description 统一现代异步基建工具集（Promise.withResolvers & Promise.try 单源收敛）。
 *
 * 核心契约：
 * 1. withResolvers: 优先使用 Baseline 2024 原生 Promise.withResolvers，低版本安全降级；
 * 2. promiseTry: 优先使用 Baseline 2025 原生 Promise.try，统一捕获同步抛错与异步拒付。
 */

export interface PromiseWithResolvers<T> {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
  reject: (reason?: unknown) => void
}

/**
 * 创建受控 Promise，同时解耦返回其实例与状态控制函数。
 *
 * @template T Promise 兑现结果的类型
 * @returns 包含 promise, resolve, reject 的受控元组对象
 */
export function withResolvers<T>(): PromiseWithResolvers<T> {
  if (typeof Promise.withResolvers === 'function') {
    return Promise.withResolvers<T>()
  }
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

/**
 * 包装任意同步或异步函数执行，统一将其转化为 Promise。
 * 确保即使 fn 同步抛出异常也能安全收敛为 rejected Promise，避免击穿外层调用栈。
 * 支持直接透传参数，避免在调用端创建不必要的闭包。
 *
 * @template T 函数返回结果的类型
 * @template Args 函数入参类型元组
 * @param fn 需要安全执行的同步或异步回调函数
 * @param args 透传给回调函数的参数
 * @returns 统一包装后的 Promise
 */
export function promiseTry<T, Args extends unknown[]>(
  fn: (...args: Args) => T | PromiseLike<T>,
  ...args: Args
): Promise<Awaited<T>> {
  if (typeof Promise.try === 'function') {
    return Promise.try(fn, ...args)
  }
  return new Promise<Awaited<T>>((resolve) => resolve(fn(...args) as Awaited<T>))
}

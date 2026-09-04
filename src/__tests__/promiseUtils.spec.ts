import { describe, it, expect } from 'vite-plus/test'
import { withResolvers, promiseTry } from '@/utils/promise'

describe('promise utils', () => {
  describe('withResolvers', () => {
    it('resolves controlled promise when resolve is called', async () => {
      const { promise, resolve } = withResolvers<string>()
      resolve('resolved-val')
      const result = await promise
      expect(result).toBe('resolved-val')
    })

    it('rejects controlled promise when reject is called', async () => {
      const { promise, reject } = withResolvers<number>()
      reject(new Error('fail-val'))
      await expect(promise).rejects.toThrow('fail-val')
    })

    it('settles only once idempotently', async () => {
      const { promise, resolve, reject } = withResolvers<string>()
      resolve('first-win')
      resolve('second-ignored')
      reject(new Error('ignored-reject'))
      const result = await promise
      expect(result).toBe('first-win')
    })
  })

  describe('promiseTry', () => {
    it('wraps synchronous return value into resolved promise', async () => {
      const p = promiseTry(() => 42)
      expect(p).toBeInstanceOf(Promise)
      const res = await p
      expect(res).toBe(42)
    })

    it('catches synchronous exception into rejected promise', async () => {
      const p = promiseTry(() => {
        throw new Error('sync-error')
      })
      expect(p).toBeInstanceOf(Promise)
      await expect(p).rejects.toThrow('sync-error')
    })

    it('passes through asynchronous promise resolution', async () => {
      const p = promiseTry(async () => {
        return 'async-ok'
      })
      const res = await p
      expect(res).toBe('async-ok')
    })

    it('passes through asynchronous promise rejection', async () => {
      const p = promiseTry(async () => {
        throw new Error('async-fail')
      })
      await expect(p).rejects.toThrow('async-fail')
    })

    it('passes multiple arguments directly to callback avoiding extra closures', async () => {
      const sum = (a: number, b: number, c: number) => a + b + c
      const res = await promiseTry(sum, 10, 20, 30)
      expect(res).toBe(60)
    })
  })
})

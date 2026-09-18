/**
 * @file testUtils.spec.ts
 * @description 单元测试验证 testUtils 工具库（withSetup 宿主生命周期包装器与 flushAsync 异步刷新）。
 */

import { describe, it, expect } from 'vite-plus/test'
import { ref, onMounted, onUnmounted, inject, type InjectionKey } from 'vue'
import { withSetup, flushAsync } from './testUtils'

const TEST_KEY: InjectionKey<string> = Symbol('test-token')

describe('testUtils withSetup & flushAsync', () => {
  it('correctly mounts composable and executes onMounted lifecycle hook', async () => {
    let mounted = false
    let unmounted = false

    function useLifecycleDemo() {
      const count = ref(0)
      onMounted(() => {
        mounted = true
        count.value = 42
      })
      onUnmounted(() => {
        unmounted = true
      })
      return { count }
    }

    const [result, app] = withSetup(() => useLifecycleDemo())

    expect(mounted).toBe(true)
    expect(result.count.value).toBe(42)

    app.unmount()
    expect(unmounted).toBe(true)
  })

  it('provides injected dependencies to composable', () => {
    function useInjectDemo() {
      const token = inject(TEST_KEY, 'fallback')
      return { token }
    }

    const [result, app] = withSetup(() => useInjectDemo(), {
      providers: [[TEST_KEY, 'secret-vault-123']],
    })

    expect(result.token).toBe('secret-vault-123')
    app.unmount()
  })

  it('flushes pending promises with flushAsync', async () => {
    let resolved = false
    void Promise.resolve().then(() => {
      resolved = true
    })

    expect(resolved).toBe(false)
    await flushAsync()
    expect(resolved).toBe(true)
  })
})

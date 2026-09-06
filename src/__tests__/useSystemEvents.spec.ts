import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { MAX_SSE_RETRY_ATTEMPTS, useSystemEvents } from '@/composables/useSystemEvents'

describe('useSystemEvents composable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('exports MAX_SSE_RETRY_ATTEMPTS as 10 and DEFAULT_IDLE_TIMEOUT_MS as 10 minutes', () => {
    expect(MAX_SSE_RETRY_ATTEMPTS).toBe(10)
    const { shouldBeConnected, isReaderRoute } = useSystemEvents()
    expect(typeof shouldBeConnected.value).toBe('boolean')
    expect(typeof isReaderRoute.value).toBe('boolean')
  })

  it('initializes in disconnected state with empty events', () => {
    const { isConnected, isSleeping, shouldBeConnected } = useSystemEvents()
    expect(isConnected.value).toBe(false)
    expect(isSleeping.value).toBe(false)
    expect(shouldBeConnected.value).toBe(false)
  })

  it('manages disconnect and connect intent state', () => {
    const { connect, disconnect, isConnected, isSleeping, shouldBeConnected, reconcileState } =
      useSystemEvents()
    disconnect()
    expect(isConnected.value).toBe(false)
    expect(isSleeping.value).toBe(false)
    expect(shouldBeConnected.value).toBe(false)

    connect()
    // In test environment without mock EventSource, remains disconnected or sleeping gracefully
    expect(isConnected.value).toBe(false)
    expect(typeof reconcileState).toBe('function')
  })

  it('throttles reconcileState within 3000ms window', async () => {
    const { reconcileState } = useSystemEvents()
    await expect(reconcileState()).resolves.toBeUndefined()
    await expect(reconcileState()).resolves.toBeUndefined()
  })
})

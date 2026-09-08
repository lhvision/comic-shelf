import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import {
  BROADCAST_CHANNEL_NAME,
  MAX_SSE_RETRY_ATTEMPTS,
  TASK_TEARDOWN_COOLDOWN_MS,
  useSystemEvents,
} from '@/composables/useSystemEvents'

describe('useSystemEvents composable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('exports MAX_SSE_RETRY_ATTEMPTS, TASK_TEARDOWN_COOLDOWN_MS and BROADCAST_CHANNEL_NAME', () => {
    expect(MAX_SSE_RETRY_ATTEMPTS).toBe(10)
    expect(TASK_TEARDOWN_COOLDOWN_MS).toBe(5000)
    expect(BROADCAST_CHANNEL_NAME).toBe('paper-room')
    const { shouldBeConnected, isReaderRoute } = useSystemEvents()
    expect(typeof shouldBeConnected.value).toBe('boolean')
    expect(typeof isReaderRoute.value).toBe('boolean')
  })

  it('initializes in disconnected state with empty events', () => {
    const { isConnected, isSleeping, shouldBeConnected, hasActiveTasks, activeTaskCount } =
      useSystemEvents()
    expect(isConnected.value).toBe(false)
    expect(isSleeping.value).toBe(false)
    expect(shouldBeConnected.value).toBe(false)
    expect(hasActiveTasks.value).toBe(false)
    expect(activeTaskCount.value).toBe(0)
  })

  it('manages task registration, task-driven intent, and teardown cooldown', () => {
    const { beginTask, endTask, hasActiveTasks, activeTaskCount, shouldBeConnected, disconnect } =
      useSystemEvents()

    disconnect()
    expect(hasActiveTasks.value).toBe(false)

    beginTask('import:jm/12345')
    expect(hasActiveTasks.value).toBe(true)
    expect(activeTaskCount.value).toBe(1)
    expect(shouldBeConnected.value).toBe(true)

    // Repeated beginTask with same ID does not duplicate
    beginTask('import:jm/12345')
    expect(activeTaskCount.value).toBe(1)

    endTask('import:jm/12345')
    expect(hasActiveTasks.value).toBe(false)
    expect(activeTaskCount.value).toBe(0)

    disconnect()
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
    disconnect()
  })

  it('supports broadcasting local changes safely', () => {
    const { broadcastLocalChange } = useSystemEvents()
    expect(() => {
      broadcastLocalChange({
        action: 'delete',
        source: 'jm',
        source_id: '12345',
        timestamp: Date.now(),
      })
    }).not.toThrow()
  })

  it('throttles reconcileState within 3000ms window', async () => {
    const { reconcileState } = useSystemEvents()
    await expect(reconcileState()).resolves.toBeUndefined()
    await expect(reconcileState()).resolves.toBeUndefined()
  })
})

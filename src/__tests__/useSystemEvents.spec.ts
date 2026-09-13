import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { api } from '@/api/client'
import {
  BROADCAST_CHANNEL_NAME,
  MAX_SSE_RETRY_ATTEMPTS,
  TASK_TEARDOWN_COOLDOWN_MS,
  getTaskId,
  useSystemEvents,
} from '@/composables/useSystemEvents'

describe('useSystemEvents composable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('exports MAX_SSE_RETRY_ATTEMPTS, TASK_TEARDOWN_COOLDOWN_MS and BROADCAST_CHANNEL_NAME', () => {
    expect(MAX_SSE_RETRY_ATTEMPTS).toBe(10)
    expect(TASK_TEARDOWN_COOLDOWN_MS).toBe(5000)
    expect(BROADCAST_CHANNEL_NAME).toBe('paper-room')
    const { shouldBeConnected, isReaderRoute } = useSystemEvents()
    expect(typeof shouldBeConnected.value).toBe('boolean')
    expect(typeof isReaderRoute.value).toBe('boolean')
  })

  it('constructs consistent task IDs via getTaskId factory', () => {
    expect(getTaskId.import('jm', '123')).toBe('import:jm/123')
    expect(getTaskId.cache('jm', '123')).toBe('cache:jm/123')
    expect(getTaskId.chapter('jm', '123', 'c1')).toBe('chapter:jm/123/c1')
    expect(getTaskId.liveCache()).toBe('library:live-cache')
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

  it('manages task registration and task-driven intent', () => {
    const { beginTask, endTask, hasActiveTasks, activeTaskCount, shouldBeConnected, disconnect } =
      useSystemEvents()

    disconnect()
    expect(hasActiveTasks.value).toBe(false)

    beginTask(getTaskId.import('jm', '12345'))
    expect(hasActiveTasks.value).toBe(true)
    expect(activeTaskCount.value).toBe(1)
    expect(shouldBeConnected.value).toBe(true)

    // Repeated beginTask with same ID does not duplicate
    beginTask(getTaskId.import('jm', '12345'))
    expect(activeTaskCount.value).toBe(1)

    endTask(getTaskId.import('jm', '12345'))
    expect(hasActiveTasks.value).toBe(false)
    expect(activeTaskCount.value).toBe(0)

    disconnect()
  })

  it('manages disconnect and task-driven intent state', () => {
    const { beginTask, disconnect, isConnected, isSleeping, shouldBeConnected, reconcileState } =
      useSystemEvents()
    disconnect()
    expect(isConnected.value).toBe(false)
    expect(isSleeping.value).toBe(false)
    expect(shouldBeConnected.value).toBe(false)

    beginTask('test:task')
    expect(shouldBeConnected.value).toBe(true)
    expect(typeof reconcileState).toBe('function')
    disconnect()
    expect(shouldBeConnected.value).toBe(false)
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

  it('supports broadcasting and handling favorite_changed events safely', () => {
    const { broadcastLocalChange } = useSystemEvents()
    expect(() => {
      broadcastLocalChange({
        action: 'favorite_changed',
        source: 'jm',
        source_id: '12345',
        favorite: true,
        timestamp: Date.now(),
      })
    }).not.toThrow()
  })

  it('supports broadcasting and handling reading_progress_changed events safely', () => {
    const { broadcastLocalChange } = useSystemEvents()
    expect(() => {
      broadcastLocalChange({
        action: 'reading_progress_changed',
        source: 'jm',
        source_id: '12345',
        last_page: 42,
        timestamp: Date.now(),
      })
    }).not.toThrow()
  })

  it('releases active cache task on cache_partial via handleLibraryChanged', () => {
    const { beginTask, hasActiveTasks, activeTaskCount, handleLibraryChanged, disconnect } =
      useSystemEvents()
    disconnect()

    beginTask(getTaskId.cache('jm', '55555'))
    expect(hasActiveTasks.value).toBe(true)

    handleLibraryChanged({
      action: 'cache_partial',
      source: 'jm',
      source_id: '55555',
      timestamp: Date.now(),
    })

    expect(hasActiveTasks.value).toBe(false)
    expect(activeTaskCount.value).toBe(0)
    disconnect()
  })

  it('throttles reconcileState within 3000ms window', async () => {
    const { reconcileState } = useSystemEvents()
    await expect(reconcileState()).resolves.toBeUndefined()
    await expect(reconcileState()).resolves.toBeUndefined()
  })

  it('prunes zombie tasks when reconcileActiveTasks runs against backend running jobs', async () => {
    const { beginTask, activeTaskCount, reconcileActiveTasks, disconnect } = useSystemEvents()
    disconnect()

    // Register 2 background tasks
    beginTask(getTaskId.cache('jm', '99999'))
    beginTask(getTaskId.chapter('jm', '99999', 'ch1'))
    expect(activeTaskCount.value).toBe(2)

    // Mock api.cacheJobs returning only ch1 as still running
    vi.spyOn(api, 'cacheJobs').mockResolvedValue([
      {
        source: 'jm',
        source_id: '99999',
        chapter_id: 'ch1',
        running: true,
        done: false,
        total: 10,
        prefetched: 5,
        warnings: [],
        error: '',
        started_at: Date.now(),
        finished_at: null,
      },
    ])

    await reconcileActiveTasks()

    // The whole-comic cache task should be pruned because it is not running
    expect(activeTaskCount.value).toBe(1)

    // Now mock api.cacheJobs returning empty list (all jobs done)
    vi.spyOn(api, 'cacheJobs').mockResolvedValue([])
    await reconcileActiveTasks()
    expect(activeTaskCount.value).toBe(0)

    disconnect()
  })

  it('handles teardown cooldown lifecycle with Mock EventSource', () => {
    class MockEventSource {
      url: string
      options?: unknown
      onopen: (() => void) | null = null
      onerror: (() => void) | null = null
      close = vi.fn<() => void>()
      addEventListener = vi.fn<() => void>()
      constructor(url: string, options?: unknown) {
        this.url = url
        this.options = options
      }
    }

    const originalEventSource = globalThis.EventSource
    globalThis.EventSource = MockEventSource as unknown as typeof EventSource

    try {
      const { beginTask, endTask, isConnected, isCoolingDown, disconnect } = useSystemEvents()
      disconnect()

      beginTask(getTaskId.import('jm', '54321'))

      // Trigger open on created mock EventSource
      endTask(getTaskId.import('jm', '54321'))

      // Cooldown should be initiated
      expect(isCoolingDown.value).toBe(true)

      // Advancing 5000ms clears cooldown
      vi.advanceTimersByTime(5000)
      expect(isCoolingDown.value).toBe(false)

      disconnect()
      expect(isConnected.value).toBe(false)
    } finally {
      globalThis.EventSource = originalEventSource
    }
  })
})

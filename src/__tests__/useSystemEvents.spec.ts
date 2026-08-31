import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { MAX_SSE_RETRY_ATTEMPTS, useSystemEvents } from '@/composables/useSystemEvents'

describe('useSystemEvents composable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('exports MAX_SSE_RETRY_ATTEMPTS as 10', () => {
    expect(MAX_SSE_RETRY_ATTEMPTS).toBe(10)
  })

  it('initializes in disconnected state with empty events', () => {
    const { isConnected, lastPing, lastVersionEvent, lastLibraryEvent, aiTasks } = useSystemEvents()
    expect(isConnected.value).toBe(false)
    expect(lastPing.value).toBeNull()
    expect(lastVersionEvent.value).toBeNull()
    expect(lastLibraryEvent.value).toBeNull()
    expect(aiTasks.value).toEqual({})
  })
})

import { describe, expect, it, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useOfflineSync } from '@/composables/useOfflineSync'
import { api } from '@/api/client'
import * as offlineDb from '@/utils/offlineDb'

describe('useOfflineSync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('records offline action into indexeddb queue', async () => {
    const enqueueSpy = vi.spyOn(offlineDb, 'enqueueOfflineAction').mockResolvedValue(1)
    const { recordOfflineAction } = useOfflineSync()

    await recordOfflineAction('favorite', { source: 'jm', sourceId: '123', favorite: true })
    expect(enqueueSpy).toHaveBeenCalledWith({
      type: 'favorite',
      payload: { source: 'jm', sourceId: '123', favorite: true },
      userId: 'default',
    })
  })

  it('flushes pending reading_progress and favorite actions when online', async () => {
    const mockActions = [
      {
        id: 1,
        userId: 'default',
        type: 'reading_progress' as const,
        payload: { source: 'jm', sourceId: '100', page: 8, total_pages: 20 },
        timestamp: Date.now(),
      },
      {
        id: 2,
        userId: 'default',
        type: 'favorite' as const,
        payload: { source: 'jm', sourceId: '200', favorite: true },
        timestamp: Date.now(),
      },
    ]

    vi.spyOn(offlineDb, 'getOfflineActions').mockResolvedValue(mockActions)
    const removeSpy = vi.spyOn(offlineDb, 'removeOfflineAction').mockResolvedValue()
    const progressSpy = vi.spyOn(api, 'saveReadingProgress').mockResolvedValue({
      ok: true,
      last_page: 8,
      total_pages: 20,
      updated_at: 0,
    })
    const favoriteSpy = vi.spyOn(api, 'setFavorite').mockResolvedValue({
      ok: true,
      favorite: true,
    })

    const { flushPendingActions } = useOfflineSync()
    await flushPendingActions()

    expect(progressSpy).toHaveBeenCalledWith('jm', '100', 8, 20)
    expect(favoriteSpy).toHaveBeenCalledWith('jm', '200', true)
    expect(removeSpy).toHaveBeenCalledWith(1)
    expect(removeSpy).toHaveBeenCalledWith(2)
  })

  it('discards non-retryable 4xx actions to prevent queue head-of-line blocking', async () => {
    const { ApiError } = await import('@/api/client')
    const mockActions = [
      {
        id: 1,
        userId: 'default',
        type: 'reading_progress' as const,
        payload: { source: 'jm', sourceId: 'deleted-comic', page: 5 },
        timestamp: Date.now(),
      },
      {
        id: 2,
        userId: 'default',
        type: 'favorite' as const,
        payload: { source: 'jm', sourceId: 'valid-comic', favorite: true },
        timestamp: Date.now(),
      },
    ]

    vi.spyOn(offlineDb, 'getOfflineActions').mockResolvedValue(mockActions)
    const removeSpy = vi.spyOn(offlineDb, 'removeOfflineAction').mockResolvedValue()
    vi.spyOn(api, 'saveReadingProgress').mockRejectedValue(new ApiError(404, 'Comic not found'))
    const favoriteSpy = vi.spyOn(api, 'setFavorite').mockResolvedValue({
      ok: true,
      favorite: true,
    })

    const { flushPendingActions } = useOfflineSync()
    await flushPendingActions()

    // Even though action 1 failed with 404, it was discarded and did not block action 2
    expect(removeSpy).toHaveBeenCalledWith(1)
    expect(favoriteSpy).toHaveBeenCalledWith('jm', 'valid-comic', true)
    expect(removeSpy).toHaveBeenCalledWith(2)
  })
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { useImageSearch } from '@/composables/useImageSearch'

describe('useImageSearch', () => {
  const revokeObjectURLMock = vi.fn<(url: string) => void>()
  const createObjectURLMock = vi.fn<() => string>(() => 'blob:test')

  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(),
    )
    vi.stubGlobal('URL', {
      createObjectURL: createObjectURLMock,
      revokeObjectURL: revokeObjectURLMock,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('checks status successfully', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ available: true, url: 'http://localhost:8765' }),
    } as unknown as Response)

    const { isAvailable, checkStatus } = useImageSearch()
    await checkStatus()

    expect(fetch).toHaveBeenCalledWith('/api/search/image/status', expect.anything())
    expect(isAvailable.value).toBe(true)
  })

  it('handles searchWithFile correctly', async () => {
    const {
      searchWithFile,
      searchImageFile,
      searchImagePreviewUrl,
      isSearching,
      searchResults,
      error,
    } = useImageSearch()

    const mockResults = [
      { source: 'jm', source_id: '123', page_index: 5, score: 0.95, is_cover: false },
    ]

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockResults,
    } as unknown as Response)

    const file = new File([''], 'test.png', { type: 'image/png' })
    const searchPromise = searchWithFile(file)

    expect(isSearching.value).toBe(true)
    expect(searchImageFile.value).toBe(file)
    expect(searchImagePreviewUrl.value).toBe('blob:test')

    await searchPromise

    expect(isSearching.value).toBe(false)
    expect(error.value).toBe('')
    expect(searchResults.value).toEqual(mockResults)
  })

  it('clears image data', async () => {
    const { searchWithFile, clearImage, searchImageFile, searchImagePreviewUrl } = useImageSearch()

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    } as unknown as Response)

    const file = new File([''], 'test.png', { type: 'image/png' })
    await searchWithFile(file)

    expect(searchImageFile.value).not.toBeNull()
    expect(searchImagePreviewUrl.value).not.toBe('')

    clearImage()

    expect(searchImageFile.value).toBeNull()
    expect(searchImagePreviewUrl.value).toBe('')
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:test')
  })

  it('caps auto retries at 3 attempts and allows manual recheck', async () => {
    vi.useFakeTimers()
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ available: false }),
    } as unknown as Response)

    const { isAvailable, checkStatus } = useImageSearch()

    // 1st attempt (initial check)
    await checkStatus()
    expect(isAvailable.value).toBe(false)
    expect(fetch).toHaveBeenCalledTimes(1)

    // 2nd attempt (after 6s)
    await vi.advanceTimersByTimeAsync(6000)
    expect(fetch).toHaveBeenCalledTimes(2)

    // 3rd attempt (after another 6s)
    await vi.advanceTimersByTimeAsync(6000)
    expect(fetch).toHaveBeenCalledTimes(3)

    // Advancing further should NOT trigger any more fetches (capped at 3)
    await vi.advanceTimersByTimeAsync(6000)
    await vi.advanceTimersByTimeAsync(60000)
    expect(fetch).toHaveBeenCalledTimes(3)

    // Manual click triggers an immediate check
    const manualResult = await checkStatus(true)
    expect(manualResult).toBe(false)
    expect(fetch).toHaveBeenCalledTimes(4)

    // Manual failed check does not resume auto polling
    await vi.advanceTimersByTimeAsync(60000)
    expect(fetch).toHaveBeenCalledTimes(4)

    vi.useRealTimers()
  })

  it('suppresses auto retry when manual check is requested during in-flight fetch', async () => {
    vi.useFakeTimers()
    let resolveFetch!: (res: Response) => void
    const pendingPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve
    })
    vi.mocked(fetch).mockReturnValue(pendingPromise)

    const { checkStatus } = useImageSearch()

    // 1st attempt starts in background (auto)
    const initialPromise = checkStatus(false)
    expect(fetch).toHaveBeenCalledTimes(1)

    // User clicks while fetch is in-flight
    const manualPromise = checkStatus(true)
    expect(fetch).toHaveBeenCalledTimes(1) // reuses in-flight

    resolveFetch({
      ok: true,
      status: 200,
      json: async () => ({ available: false }),
    } as unknown as Response)

    const [res1, res2] = await Promise.all([initialPromise, manualPromise])
    expect(res1).toBe(false)
    expect(res2).toBe(false)

    // Ensure no retry timer was scheduled because manual check was requested
    await vi.advanceTimersByTimeAsync(60000)
    expect(fetch).toHaveBeenCalledTimes(1)

    vi.useRealTimers()
  })
})

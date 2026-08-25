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
})

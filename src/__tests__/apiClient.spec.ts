/**
 * @file apiClient.spec.ts
 * @description 验证 api 客户端各端点及 buildQueryString 声明式对象过滤与 URL 查询参数组装契约。
 */

import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { api, buildQueryString, coverFileUrl, chapterCoverUrl } from '@/api/client'

function mockJsonResponse(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function getCalledUrl(mock: ReturnType<typeof vi.fn<typeof fetch>>): string {
  const arg = mock.mock.calls[0]?.[0]
  if (typeof arg === 'string') return arg
  if (arg instanceof URL) return arg.toString()
  if (
    arg &&
    typeof arg === 'object' &&
    'url' in arg &&
    typeof (arg as { url: unknown }).url === 'string'
  ) {
    return (arg as { url: string }).url
  }
  return ''
}

describe('buildQueryString object filtering', () => {
  it('filters undefined, null, and empty string entries declaratively', () => {
    expect(buildQueryString()).toBe('')
    expect(buildQueryString({})).toBe('')
    expect(
      buildQueryString({
        a: 'hello',
        b: undefined,
        c: null,
        d: '',
        num: 42,
        bool: true,
      }),
    ).toBe('a=hello&num=42&bool=true')
  })

  it('filters whitespace-only strings and correctly serializes boolean values', () => {
    expect(
      buildQueryString({
        search: '   ',
        valid: 'ok',
        flag: false,
      }),
    ).toBe('valid=ok&flag=false')
  })

  it('joins array values into comma-separated strings', () => {
    expect(
      buildQueryString({
        tags: ['纯爱', '全彩', '  ', ''],
        emptyArray: [],
      }),
    ).toBe('tags=%E7%BA%AF%E7%88%B1%2C%E5%85%A8%E5%BD%A9')
  })
})

describe('api client query assembly', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('assembles library query parameters cleanly without undefined or default values', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      mockJsonResponse({
        items: [],
        total: 0,
        page: 1,
        page_size: 24,
        has_more: false,
      }),
    )
    globalThis.fetch = fetchMock

    await api.library({
      page: 2,
      page_size: 48,
      source: 'jm',
      search: '同人',
      tags: '纯爱,全彩',
      status: 'all', // Should be omitted since 'all' is default
      sort: 'recent', // Should be omitted since 'recent' is default
      favorite: false, // Should be omitted since falsy
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const calledUrl = getCalledUrl(fetchMock)
    expect(calledUrl).toContain('/library?')
    expect(calledUrl).toContain('page=2')
    expect(calledUrl).toContain('page_size=48')
    expect(calledUrl).toContain('source=jm')
    expect(calledUrl).toContain('q=%E5%90%8C%E4%BA%BA')
    expect(calledUrl).toContain('tags=%E7%BA%AF%E7%88%B1%2C%E5%85%A8%E5%BD%A9')
    expect(calledUrl).not.toContain('status=')
    expect(calledUrl).not.toContain('sort=')
    expect(calledUrl).not.toContain('favorite=')
  })

  it('correctly includes status, sort, and favorite when non-default', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      mockJsonResponse({
        items: [],
        total: 0,
        page: 1,
        page_size: 24,
        has_more: false,
      }),
    )
    globalThis.fetch = fetchMock

    await api.library({
      status: 'reading',
      sort: 'pages',
      favorite: true,
    })

    const calledUrl = getCalledUrl(fetchMock)
    expect(calledUrl).toContain('status=reading')
    expect(calledUrl).toContain('sort=pages')
    expect(calledUrl).toContain('favorite=true')
  })

  it('correctly falls back to tag when tags is empty string', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      mockJsonResponse({
        items: [],
        total: 0,
        page: 1,
        page_size: 24,
        has_more: false,
      }),
    )
    globalThis.fetch = fetchMock

    await api.library({
      tags: '',
      tag: '单标签',
    })

    const calledUrl = getCalledUrl(fetchMock)
    expect(calledUrl).toContain('tags=%E5%8D%95%E6%A0%87%E7%AD%BE')
  })

  it('assembles libraryFacets query parameters cleanly', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      mockJsonResponse({
        total: 0,
        reading: 0,
        completed: 0,
        favorites: 0,
        tags: [],
      }),
    )
    globalThis.fetch = fetchMock

    await api.libraryFacets('picacg')
    const calledUrl = getCalledUrl(fetchMock)
    expect(calledUrl).toContain('/library/facets?source=picacg')
  })

  it('assembles uploadPages and replaceComicPages query parameters via declarative object filtering', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(
        mockJsonResponse({
          source: 'local',
          source_id: 'test_id',
        }),
      ),
    )
    globalThis.fetch = fetchMock

    const testFile = new File(['dummy'], 'page1.jpg', { type: 'image/jpeg' })

    // 1. With chapter and title
    await api.uploadPages('local', 'test_id', [testFile], 'chap_1', '第一话')
    expect(getCalledUrl(fetchMock)).toContain('/library/local/test_id/upload-pages?')
    expect(getCalledUrl(fetchMock)).toContain('chapter_id=chap_1')
    expect(getCalledUrl(fetchMock)).toContain('new_chapter_title=%E7%AC%AC%E4%B8%80%E8%AF%9D')

    // 2. Without chapter or title -> zero query string
    fetchMock.mockClear()
    await api.uploadPages('local', 'test_id', [testFile])
    expect(getCalledUrl(fetchMock)).toBe('/api/library/local/test_id/upload-pages')

    // 3. replaceComicPages with chapter
    fetchMock.mockClear()
    await api.replaceComicPages('local', 'test_id', [testFile], 'chap_2')
    expect(getCalledUrl(fetchMock)).toContain(
      '/library/local/test_id/replace-pages?chapter_id=chap_2',
    )

    // 4. replaceComicPages without chapter -> zero query string
    fetchMock.mockClear()
    await api.replaceComicPages('local', 'test_id', [testFile])
    expect(getCalledUrl(fetchMock)).toBe('/api/library/local/test_id/replace-pages')
  })

  it('assembles discoveryRanking query parameters via declarative object filtering', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(
        mockJsonResponse({
          items: [],
        }),
      ),
    )
    globalThis.fetch = fetchMock

    // Without refresh
    await api.discoveryRanking('month', false)
    expect(getCalledUrl(fetchMock)).toBe('/api/discovery/ranking?timeframe=month')

    // With refresh
    fetchMock.mockClear()
    await api.discoveryRanking('day', true)
    expect(getCalledUrl(fetchMock)).toBe('/api/discovery/ranking?timeframe=day&refresh=true')

    // With undefined timeframe and refresh=true
    fetchMock.mockClear()
    await api.discoveryRanking(undefined, true)
    expect(getCalledUrl(fetchMock)).toBe('/api/discovery/ranking?timeframe=week&refresh=true')

    // With explicit source
    fetchMock.mockClear()
    await api.discoveryRanking('picacg', 'week', false)
    expect(getCalledUrl(fetchMock)).toBe('/api/discovery/ranking?source=picacg&timeframe=week')

    // With explicit source, undefined timeframe, and refresh=true
    fetchMock.mockClear()
    await api.discoveryRanking('picacg', undefined, true)
    expect(getCalledUrl(fetchMock)).toBe(
      '/api/discovery/ranking?source=picacg&timeframe=week&refresh=true',
    )
  })

  it('assembles coverFileUrl and chapterCoverUrl via buildQueryString', () => {
    expect(coverFileUrl('jm', '12345', 1)).toBe('/api/library/jm/12345/covers/1/file.webp')
    expect(coverFileUrl('jm', '12345', 1, 360)).toBe(
      '/api/library/jm/12345/covers/1/file.webp?w=360',
    )

    expect(chapterCoverUrl('jm', '12345', 'c1')).toBe(
      '/api/library/jm/12345/chapters/c1/cover.webp',
    )
    expect(chapterCoverUrl('jm', '12345', 'c1', 720)).toBe(
      '/api/library/jm/12345/chapters/c1/cover.webp?w=720',
    )
  })
})

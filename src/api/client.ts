import { useMemoize } from '@vueuse/core'
import type {
  CacheJob,
  CacheProgress,
  ComicDetail,
  DownloadConcurrency,
  ImportRequest,
  ImportResult,
  LibrarySummary,
  ProviderInfo,
} from '@/types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')

  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    let detail = `请求失败（${response.status}）`
    try {
      const body = (await response.json()) as { detail?: string; message?: string }
      detail = body.detail || body.message || detail
    } catch {
      /* keep default message */
    }
    throw new Error(detail)
  }

  return (await response.json()) as T
}

const memoizedDetail = useMemoize(
  (source: string, sourceId: string) => request<ComicDetail>(`/library/${source}/${sourceId}`),
  { getKey: (source, sourceId) => `${source}/${sourceId}` },
)

const memoizedProviders = useMemoize(() => request<ProviderInfo[]>('/providers'))

export const api = {
  health: () => request<{ ok: boolean }>('/health'),
  providers: memoizedProviders,
  library: () => request<LibrarySummary[]>('/library'),
  detail: memoizedDetail,
  importComic: async (payload: ImportRequest) => {
    memoizedDetail.clear()
    return request<ImportResult>('/library/import', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  deleteComic: async (source: string, sourceId: string) => {
    memoizedDetail.delete(source, sourceId)
    return request<{ ok: boolean }>(`/library/${source}/${sourceId}`, {
      method: 'DELETE',
    })
  },
  setFavorite: async (source: string, sourceId: string, favorite: boolean) => {
    memoizedDetail.delete(source, sourceId)
    return request<{ ok: boolean; favorite: boolean }>(`/library/${source}/${sourceId}/favorite`, {
      method: 'PATCH',
      body: JSON.stringify({ favorite }),
    })
  },
  cacheAll: async (source: string, sourceId: string) => {
    memoizedDetail.delete(source, sourceId)
    return request<CacheProgress>(`/library/${source}/${sourceId}/cache`, {
      method: 'POST',
      body: '{}',
    })
  },
  cacheProgress: (source: string, sourceId: string) =>
    request<CacheProgress>(`/library/${source}/${sourceId}/cache`),
  cacheJob: (source: string, sourceId: string) =>
    request<CacheJob>(`/library/${source}/${sourceId}/cache/job`),
  cacheJobs: () => request<CacheJob[]>('/cache/jobs'),
  downloadConcurrency: () => request<DownloadConcurrency>('/settings/download-concurrency'),
  setDownloadConcurrency: (limit: number) =>
    request<DownloadConcurrency>('/settings/download-concurrency', {
      method: 'PUT',
      body: JSON.stringify({ limit }),
    }),
}

export const pageFileUrl = (source: string, sourceId: string, index: number) =>
  `${BASE}/library/${source}/${sourceId}/pages/${index}/file`

export const pageThumbUrl = (source: string, sourceId: string, index: number) =>
  `${BASE}/library/${source}/${sourceId}/pages/${index}/thumbnail`

export const coverFileUrl = (source: string, sourceId: string, index: number) =>
  `${BASE}/library/${source}/${sourceId}/covers/${index}/file`

// T17：章节目录封面端点（后端按章节 id 定位，从该话第一页生成并池化缓存）
export const chapterCoverUrl = (source: string, sourceId: string, chapterId: string) =>
  `${BASE}/library/${source}/${sourceId}/chapters/${chapterId}/cover`

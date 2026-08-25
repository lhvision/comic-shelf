import { useMemoize } from '@vueuse/core'
import type {
  AuthStatus,
  CacheJob,
  CacheProgress,
  ComicDetail,
  DownloadConcurrency,
  ImportRequest,
  ImportResult,
  LibrarySummary,
  LoginResult,
  ProviderInfo,
} from '@/types'

const BASE = '/api'
const TOKEN_STORAGE_KEY = 'comic-shelf:auth-token'

export function getStoredToken(): string {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

export function setStoredToken(token: string): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // ignore
  }
}

type UnauthorizedHandler = () => void
const unauthorizedHandlers = new Set<UnauthorizedHandler>()

export function onUnauthorized(handler: UnauthorizedHandler): () => void {
  unauthorizedHandlers.add(handler)
  return () => unauthorizedHandlers.delete(handler)
}

export function notifyUnauthorized(): void {
  for (const handler of unauthorizedHandlers) {
    try {
      handler()
    } catch {
      // ignore
    }
  }
}

type AuthSuccessHandler = () => void
const authSuccessHandlers = new Set<AuthSuccessHandler>()

export function onAuthSuccess(handler: AuthSuccessHandler): () => void {
  authSuccessHandlers.add(handler)
  return () => authSuccessHandlers.delete(handler)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type') && !(init?.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const token = getStoredToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
    credentials: 'same-origin',
  })

  if (!response.ok) {
    if (response.status === 401) {
      notifyUnauthorized()
    }
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

export function clearApiCaches(): void {
  memoizedDetail.clear()
  memoizedProviders.clear()
}

export function notifyAuthSuccess(): void {
  clearApiCaches()
  for (const handler of authSuccessHandlers) {
    try {
      handler()
    } catch {
      // ignore
    }
  }
}

export const api = {
  health: () => request<{ ok: boolean; auth_required?: boolean }>('/health'),
  authStatus: () => request<AuthStatus>('/auth/status'),
  login: (secret: string) =>
    request<LoginResult>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ secret }),
    }),

  logout: () =>
    request<{ ok: boolean }>('/auth/logout', {
      method: 'POST',
    }),
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
  updateMetadata: async (
    source: string,
    sourceId: string,
    payload: import('@/types').MetadataUpdatePayload,
  ) => {
    memoizedDetail.delete(source, sourceId)
    return request<ComicDetail>(`/library/${source}/${sourceId}/metadata`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },
  createLocalComic: async (payload: import('@/types').LocalComicCreatePayload) => {
    memoizedDetail.clear()
    return request<ComicDetail>('/library/local/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  importLocalPath: async (payload: import('@/types').LocalPathImportPayload) => {
    memoizedDetail.clear()
    return request<ComicDetail>('/library/local/import-path', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  uploadLocalPages: async (
    sourceId: string,
    files: File[],
    chapterId = '',
    newChapterTitle = '',
  ) => {
    memoizedDetail.delete('local', sourceId)
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }
    const params = new URLSearchParams()
    if (chapterId) params.set('chapter_id', chapterId)
    if (newChapterTitle) params.set('new_chapter_title', newChapterTitle)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return request<ComicDetail>(`/library/local/${sourceId}/upload-pages${qs}`, {
      method: 'POST',
      body: formData,
    })
  },
  appendLocalComic: async (sourceId: string, payload: import('@/types').LocalAppendPayload) => {
    memoizedDetail.delete('local', sourceId)
    return request<ComicDetail>(`/library/local/${sourceId}/append`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  discoveryRanking: (timeframe: import('@/types').DiscoveryTimeframe = 'week', refresh = false) =>
    request<import('@/types').DiscoveryFeed>(
      `/discovery/ranking?timeframe=${encodeURIComponent(timeframe)}${refresh ? '&refresh=true' : ''}`,
    ),
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

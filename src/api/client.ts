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

export interface RequestOptions {
  signal?: AbortSignal
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function combineSignals(
  timeoutMs: number,
  callerSignal?: AbortSignal | null,
): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController()
  const timer = setTimeout(() => {
    controller.abort(new DOMException('请求超时，请重试', 'TimeoutError'))
  }, timeoutMs)

  let onAbort: (() => void) | null = null
  if (callerSignal) {
    if (callerSignal.aborted) {
      clearTimeout(timer)
      controller.abort(callerSignal.reason)
    } else {
      onAbort = () => {
        clearTimeout(timer)
        controller.abort(callerSignal.reason)
      }
      callerSignal.addEventListener('abort', onAbort, { once: true })
    }
  }

  const cleanup = () => {
    clearTimeout(timer)
    if (callerSignal && onAbort) {
      callerSignal.removeEventListener('abort', onAbort)
    }
  }

  return { signal: controller.signal, cleanup }
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

  const { signal, cleanup } = combineSignals(15000, init?.signal)
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      headers,
      signal,
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
      throw new ApiError(response.status, detail)
    }

    return (await response.json()) as T
  } finally {
    cleanup()
  }
}

const memoizedDetail = useMemoize(
  async (source: string, sourceId: string, options?: RequestOptions): Promise<ComicDetail> => {
    try {
      return await request<ComicDetail>(`/library/${source}/${sourceId}`, {
        signal: options?.signal,
      })
    } catch (e) {
      memoizedDetail.delete(source, sourceId)
      throw e
    }
  },
  {
    getKey: (source: string, sourceId: string, _options?: RequestOptions) =>
      `${source}/${sourceId}`,
  },
)

const memoizedProviders = useMemoize(async (options?: RequestOptions): Promise<ProviderInfo[]> => {
  try {
    return await request<ProviderInfo[]>('/providers', {
      signal: options?.signal,
    })
  } catch (e) {
    memoizedProviders.clear()
    throw e
  }
})

export function clearApiDetailCache(source?: string, sourceId?: string): void {
  if (source && sourceId) {
    memoizedDetail.delete(source, sourceId)
  } else {
    memoizedDetail.clear()
  }
}

export function clearApiCaches(): void {
  clearApiDetailCache()
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
  health: (options?: RequestOptions) =>
    request<{ ok: boolean; auth_required?: boolean }>('/health', {
      signal: options?.signal,
    }),
  authStatus: (options?: RequestOptions) =>
    request<AuthStatus>('/auth/status', {
      signal: options?.signal,
    }),
  login: (secret: string, pin?: string, username?: string) =>
    request<LoginResult>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ secret, pin, username }),
    }),
  claimPass: (payload: import('@/types').ClaimGuestPassPayload) =>
    request<LoginResult>('/auth/claim', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  logout: () =>
    request<{ ok: boolean }>('/auth/logout', {
      method: 'POST',
    }),
  providers: (options?: RequestOptions) => memoizedProviders(options),
  library: (options?: RequestOptions) =>
    request<LibrarySummary[]>('/library', {
      signal: options?.signal,
    }),
  detail: (source: string, sourceId: string, options?: RequestOptions) =>
    memoizedDetail(source, sourceId, options),
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
  cacheProgress: (source: string, sourceId: string, options?: RequestOptions) =>
    request<CacheProgress>(`/library/${source}/${sourceId}/cache`, {
      signal: options?.signal,
    }),
  chapterCacheProgress: (
    source: string,
    sourceId: string,
    chapterId: string,
    options?: RequestOptions,
  ) =>
    request<CacheProgress>(`/library/${source}/${sourceId}/chapters/${chapterId}/cache`, {
      signal: options?.signal,
    }),
  cacheChapter: (source: string, sourceId: string, chapterId: string, options?: RequestOptions) =>
    request<CacheProgress>(`/library/${source}/${sourceId}/chapters/${chapterId}/cache`, {
      method: 'POST',
      signal: options?.signal,
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    }),
  cacheJob: (source: string, sourceId: string, options?: RequestOptions) =>
    request<CacheJob>(`/library/${source}/${sourceId}/cache/job`, {
      signal: options?.signal,
    }),
  cacheJobs: (options?: RequestOptions) =>
    request<CacheJob[]>('/cache/jobs', {
      signal: options?.signal,
    }),
  downloadConcurrency: (options?: RequestOptions) =>
    request<DownloadConcurrency>('/settings/download-concurrency', {
      signal: options?.signal,
    }),
  setDownloadConcurrency: (limit: number) =>
    request<DownloadConcurrency>('/settings/download-concurrency', {
      method: 'PUT',
      body: JSON.stringify({ limit }),
    }),
  guestPrivacy: (options?: RequestOptions) =>
    request<import('@/types').GuestPrivacySettings>('/settings/guest-privacy', {
      signal: options?.signal,
    }),
  setGuestPrivacy: (guest_hide_new_comics: boolean) =>
    request<import('@/types').GuestPrivacySettings>('/settings/guest-privacy', {
      method: 'PUT',
      body: JSON.stringify({ guest_hide_new_comics }),
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
  replaceComicPages: async (
    source: string,
    sourceId: string,
    files: File[],
    chapterId = '',
    options?: RequestOptions,
  ) => {
    memoizedDetail.delete(source, sourceId)
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }
    const params = new URLSearchParams()
    if (chapterId) params.set('chapter_id', chapterId)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return request<ComicDetail>(`/library/${source}/${sourceId}/replace-pages${qs}`, {
      method: 'POST',
      body: formData,
      signal: options?.signal,
    })
  },
  replaceComicPagesFromPath: async (
    source: string,
    sourceId: string,
    serverPath: string,
    chapterId = '',
    options?: RequestOptions,
  ) => {
    memoizedDetail.delete(source, sourceId)
    return request<ComicDetail>(`/library/${source}/${sourceId}/replace-path`, {
      method: 'POST',
      body: JSON.stringify({
        server_path: serverPath,
        target_chapter: chapterId,
      }),
      signal: options?.signal,
    })
  },
  appendLocalComic: async (sourceId: string, payload: import('@/types').LocalAppendPayload) => {
    memoizedDetail.delete('local', sourceId)
    return request<ComicDetail>(`/library/local/${sourceId}/append`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  updateChapter: async (source: string, sourceId: string, chapterId: string, title: string) => {
    memoizedDetail.delete(source, sourceId)
    return request<ComicDetail>(
      `/library/${source}/${sourceId}/chapters/${encodeURIComponent(chapterId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ title }),
      },
    )
  },
  deleteChapter: async (source: string, sourceId: string, chapterId: string) => {
    memoizedDetail.delete(source, sourceId)
    return request<ComicDetail>(
      `/library/${source}/${sourceId}/chapters/${encodeURIComponent(chapterId)}`,
      {
        method: 'DELETE',
      },
    )
  },
  discoveryRanking: (
    timeframe: import('@/types').DiscoveryTimeframe = 'week',
    refresh = false,
    options?: RequestOptions,
  ) =>
    request<import('@/types').DiscoveryFeed>(
      `/discovery/ranking?timeframe=${encodeURIComponent(timeframe)}${refresh ? '&refresh=true' : ''}`,
      { signal: options?.signal },
    ),
  imageSearchStatus: (options?: RequestOptions) =>
    request<import('@/types').ImageSearchStatus>('/search/image/status', {
      signal: options?.signal,
    }),
  imageSearch: async (file: File, options?: RequestOptions) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<import('@/types').ImageSearchResultItem[]>('/search/image', {
      method: 'POST',
      body: formData,
      signal: options?.signal,
    })
  },
  getReadingProgress: (source: string, sourceId: string, options?: RequestOptions) =>
    request<import('@/types').ReadingProgressInfo>(`/library/${source}/${sourceId}/progress`, {
      signal: options?.signal,
    }),
  saveReadingProgress: (
    source: string,
    sourceId: string,
    page: number,
    total_pages?: number,
    options?: RequestOptions,
  ) =>
    request<import('@/types').ReadingProgressInfo>(`/library/${source}/${sourceId}/progress`, {
      method: 'PUT',
      body: JSON.stringify({ page, total_pages }),
      signal: options?.signal,
    }),
  getCuratorPasses: (options?: RequestOptions) =>
    request<import('@/types').GuestPass[]>('/curator/passes', {
      signal: options?.signal,
    }),
  createCuratorPass: (
    payload: import('@/types').CreateGuestPassPayload,
    options?: RequestOptions,
  ) =>
    request<import('@/types').GuestPass>('/curator/passes', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal: options?.signal,
    }),
  updateCuratorPass: (
    passId: number,
    payload: import('@/types').UpdateGuestPassPayload,
    options?: RequestOptions,
  ) =>
    request<import('@/types').GuestPass>(`/curator/passes/${passId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
      signal: options?.signal,
    }),
  deleteCuratorPass: (passId: number, options?: RequestOptions) =>
    request<{ ok: boolean }>(`/curator/passes/${passId}`, {
      method: 'DELETE',
      signal: options?.signal,
    }),
  deleteCuratorPassDevice: (passId: number, deviceId: number, options?: RequestOptions) =>
    request<{ ok: boolean }>(`/curator/passes/${passId}/devices/${deviceId}`, {
      method: 'DELETE',
      signal: options?.signal,
    }),
}

export const pageFileUrl = (source: string, sourceId: string, index: number) =>
  `${BASE}/library/${source}/${sourceId}/pages/${index}/file.webp`

export const pageThumbUrl = (source: string, sourceId: string, index: number) =>
  `${BASE}/library/${source}/${sourceId}/pages/${index}/thumbnail.jpg`

export const coverFileUrl = (source: string, sourceId: string, index: number, width?: number) => {
  const base = `${BASE}/library/${source}/${sourceId}/covers/${index}/file.jpg`
  return width ? `${base}?w=${width}` : base
}

// T17：章节目录封面端点（后端按章节 id 定位，从该话第一页生成并池化缓存）
export const chapterCoverUrl = (
  source: string,
  sourceId: string,
  chapterId: string,
  width?: number,
) => {
  const base = `${BASE}/library/${source}/${sourceId}/chapters/${chapterId}/cover.jpg`
  return width ? `${base}?w=${width}` : base
}

/** 为图片/封面 URL 安全附加宽度参数（?w=360 或 &w=360） */
export const withWidth = (url: string, width: number): string => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}w=${width}`
}

/** 生成符合 HTML5 规范的响应式封面 srcset 字符串（默认 360w 阶梯 + 720w 高保真原图） */
export const coverSrcset = (url: string, thumbWidth = 360, fullWidth = 720): string => {
  if (!url) return ''
  return `${withWidth(url, thumbWidth)} ${thumbWidth}w, ${url} ${fullWidth}w`
}

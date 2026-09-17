import { useMemoize } from '@vueuse/core'
import { promiseTry } from '@/utils/promise'
import type {
  AuthStatus,
  CacheJob,
  CacheProgress,
  ClaimGuestPassPayload,
  ComicAppendPayload,
  ComicDetail,
  CreateFromStagedPdfPayload,
  CreateGuestPassPayload,
  DialogueSearchResponse,
  DiscoveryFeed,
  DiscoveryTimeframe,
  DownloadConcurrency,
  GuestPass,
  GuestPrivacySettings,
  ImageSearchResultItem,
  ImageSearchStatus,
  ImportRequest,
  ImportResult,
  LibraryFacetsResponse,
  LibraryPageResponse,
  LibraryQueryParams,
  LocalComicCreatePayload,
  LocalPathImportPayload,
  LoginResult,
  MetadataUpdatePayload,
  PdfInspectResponse,
  ProviderInfo,
  ReadingProgressInfo,
  UpdateGuestPassPayload,
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

type UnauthorizedHandler = () => void | Promise<void>
const unauthorizedHandlers = new Set<UnauthorizedHandler>()

export function onUnauthorized(handler: UnauthorizedHandler): () => void {
  unauthorizedHandlers.add(handler)
  return () => unauthorizedHandlers.delete(handler)
}

export function notifyUnauthorized(): void {
  for (const handler of unauthorizedHandlers) {
    promiseTry(handler).catch(() => {})
  }
}

type AuthSuccessHandler = () => void | Promise<void>
const authSuccessHandlers = new Set<AuthSuccessHandler>()

export function onAuthSuccess(handler: AuthSuccessHandler): () => void {
  authSuccessHandlers.add(handler)
  return () => authSuccessHandlers.delete(handler)
}

export type QueryParamValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryParamValue | QueryParamValue[]>

export interface RequestOptions {
  signal?: AbortSignal
  bypassCache?: boolean
  timeoutMs?: number
  params?: QueryParams
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

/**
 * 聚合请求超时信号与调用方的主动取消信号。
 *
 * 架构考量（避坑防泄漏）：
 * 1. 为什么不裸用 `AbortSignal.timeout()`？
 *    MDN 明确指出 `AbortSignal.timeout()` 无法被外部手动取消。在短生命周期 RPC 中，
 *    即便请求 10ms 兑现，底层系统定时器仍会在后台挂满定时时长并持有监听引用，高频请求下阻碍 GC。
 *    因此超时控制采用 `AbortController` + `clearTimeout(timer)` 可控生命周期；
 * 2. 信号合成采用原生 Baseline 2024 `AbortSignal.any()`：
 *    当传入 callerSignal 时，由浏览器引擎底层自动联合监听多个信号，彻底消除手动
 *    `addEventListener('abort')` 与 `removeEventListener` 的胶水代码与事件监听器泄漏风险；
 * 3. 旧版环境自动降级至安全事件监听兜底。
 */
function combineSignals(
  timeoutMs: number,
  callerSignal?: AbortSignal | null,
): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController()
  const timer = setTimeout(() => {
    controller.abort(new DOMException('请求超时，请重试', 'TimeoutError'))
  }, timeoutMs)

  const cleanup = () => {
    clearTimeout(timer)
  }

  if (!callerSignal) {
    return { signal: controller.signal, cleanup }
  }

  if (callerSignal.aborted) {
    clearTimeout(timer)
    controller.abort(callerSignal.reason)
    return { signal: controller.signal, cleanup }
  }

  // 现代环境：原生复合信号合成，由引擎底层调度
  if (typeof AbortSignal !== 'undefined' && 'any' in AbortSignal) {
    return {
      signal: AbortSignal.any([controller.signal, callerSignal]),
      cleanup,
    }
  }

  // 旧版降级：传统一次性事件监听
  const onAbort = () => {
    clearTimeout(timer)
    controller.abort(callerSignal.reason)
  }
  callerSignal.addEventListener('abort', onAbort, { once: true })

  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timer)
      callerSignal.removeEventListener('abort', onAbort)
    },
  }
}

/**
 * 纯函数：声明式过滤对象中的 undefined、null、空字符串，
 * 将数组展开为逗号分隔字符串，生成符合规范的 URL 查询字符串。
 */
export function buildQueryString(params?: QueryParams): string {
  if (!params) return ''
  const entries: [string, string][] = []
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === null || val === '') continue
    if (Array.isArray(val)) {
      const filtered = val.filter((item) => item !== undefined && item !== null && item !== '')
      if (filtered.length > 0) {
        entries.push([key, filtered.map(String).join(',')])
      }
    } else {
      entries.push([key, String(val)])
    }
  }
  if (entries.length === 0) return ''
  return new URLSearchParams(entries).toString()
}

async function request<T>(path: string, init?: RequestInit, options?: RequestOptions): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type') && !(init?.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const token = getStoredToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const timeout = options?.timeoutMs ?? 15000
  const callerSignal = options?.signal ?? init?.signal
  const { signal, cleanup } = combineSignals(timeout, callerSignal)

  let fullPath = `${BASE}${path}`
  if (options?.params) {
    const qs = buildQueryString(options.params)
    if (qs) {
      fullPath += (fullPath.includes('?') ? '&' : '?') + qs
    }
  }

  try {
    const response = await fetch(fullPath, {
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

export const DEFAULT_PROVIDERS: ProviderInfo[] = [
  {
    key: 'jm',
    label: '禁漫天堂',
    short_label: '禁漫',
    id_pattern: '^(?:JM)?\\d+$',
    example: '523607',
    description: '禁漫天堂 (18comic)',
  },
  {
    key: 'picacg',
    label: '哔咔漫画',
    short_label: '哔咔',
    id_pattern: '^[0-9a-fA-F]{24}$',
    example: '5ebe89bf63918511c2c362a7',
    description: '哔咔漫画 (PicAcg)',
  },
  {
    key: 'local',
    label: '本地自建',
    short_label: '本地',
    id_pattern: '^[\\w\\.\\-]+$',
    example: 'my-album-01',
    description: '本地自建画集',
  },
]

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
    promiseTry(handler).catch(() => {})
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
  claimPass: (payload: ClaimGuestPassPayload) =>
    request<LoginResult>('/auth/claim', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  logout: () =>
    request<{ ok: boolean }>('/auth/logout', {
      method: 'POST',
    }),
  providers: (options?: RequestOptions) => memoizedProviders(options),
  library: (params?: LibraryQueryParams, options?: RequestOptions) => {
    return request<LibraryPageResponse>(
      '/library',
      { signal: options?.signal },
      {
        ...options,
        params: {
          page: params?.page,
          page_size: params?.page_size,
          offset: params?.offset,
          ids: params?.ids?.trim(),
          status: params?.status !== 'all' ? params?.status : undefined,
          favorite: params?.favorite ? 'true' : undefined,
          source: params?.source,
          q: (params?.q ?? params?.search)?.trim(),
          tags: (params?.tags || params?.tag)?.trim(),
          sort: params?.sort !== 'recent' ? params?.sort : undefined,
        },
      },
    )
  },
  libraryFacets: (source?: string, options?: RequestOptions) =>
    request<LibraryFacetsResponse>(
      '/library/facets',
      { signal: options?.signal },
      { ...options, params: { source } },
    ),
  detail: (source: string, sourceId: string, options?: RequestOptions) => {
    if (options?.bypassCache) {
      memoizedDetail.delete(source, sourceId)
    }
    return memoizedDetail(source, sourceId, options)
  },
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
  cacheChapter: async (
    source: string,
    sourceId: string,
    chapterId: string,
    options?: RequestOptions,
  ) => {
    memoizedDetail.delete(source, sourceId)
    return request<CacheProgress>(`/library/${source}/${sourceId}/chapters/${chapterId}/cache`, {
      method: 'POST',
      signal: options?.signal,
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
  },
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
    request<GuestPrivacySettings>('/settings/guest-privacy', {
      signal: options?.signal,
    }),
  setGuestPrivacy: (guest_hide_new_comics: boolean) =>
    request<GuestPrivacySettings>('/settings/guest-privacy', {
      method: 'PUT',
      body: JSON.stringify({ guest_hide_new_comics }),
    }),
  updateMetadata: async (source: string, sourceId: string, payload: MetadataUpdatePayload) => {
    memoizedDetail.delete(source, sourceId)
    return request<ComicDetail>(`/library/${source}/${sourceId}/metadata`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },
  createLocalComic: async (payload: LocalComicCreatePayload, options?: RequestOptions) => {
    memoizedDetail.clear()
    return request<ComicDetail>(
      '/library/local/create',
      {
        method: 'POST',
        body: JSON.stringify(payload),
        signal: options?.signal,
      },
      { timeoutMs: 60000, ...options },
    )
  },
  importLocalPath: async (payload: LocalPathImportPayload, options?: RequestOptions) => {
    memoizedDetail.clear()
    return request<ComicDetail>(
      '/library/local/import-path',
      {
        method: 'POST',
        body: JSON.stringify(payload),
        signal: options?.signal,
      },
      { timeoutMs: 120000, ...options },
    )
  },
  inspectPdf: async (formData: FormData, options?: RequestOptions) => {
    return request<PdfInspectResponse>(
      '/library/local/inspect-pdf',
      {
        method: 'POST',
        body: formData,
        signal: options?.signal,
      },
      { timeoutMs: 180000, ...options },
    )
  },
  deleteStagedPdf: async (stagingToken: string, options?: RequestOptions) => {
    return request<{ ok: boolean }>(
      `/library/local/staged-pdf/${encodeURIComponent(stagingToken)}`,
      {
        method: 'DELETE',
        signal: options?.signal,
      },
      options,
    )
  },
  createFromStagedPdf: async (payload: CreateFromStagedPdfPayload, options?: RequestOptions) => {
    memoizedDetail.clear()
    return request<ComicDetail>(
      '/library/local/create-from-staged-pdf',
      {
        method: 'POST',
        body: JSON.stringify(payload),
        signal: options?.signal,
      },
      { timeoutMs: 120000, ...options },
    )
  },
  uploadPages: async (
    source: string,
    sourceId: string,
    files: File[],
    chapterId = '',
    newChapterTitle = '',
    options?: RequestOptions,
  ) => {
    memoizedDetail.delete(source, sourceId)
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }
    return request<ComicDetail>(
      `/library/${source}/${sourceId}/upload-pages`,
      {
        method: 'POST',
        body: formData,
        signal: options?.signal,
      },
      {
        timeoutMs: 120000,
        ...options,
        params: {
          chapter_id: chapterId || undefined,
          new_chapter_title: newChapterTitle || undefined,
        },
      },
    )
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
    return request<ComicDetail>(
      `/library/${source}/${sourceId}/replace-pages`,
      {
        method: 'POST',
        body: formData,
        signal: options?.signal,
      },
      {
        timeoutMs: 120000,
        ...options,
        params: {
          chapter_id: chapterId || undefined,
        },
      },
    )
  },
  replaceComicPagesFromPath: async (
    source: string,
    sourceId: string,
    serverPath: string,
    chapterId = '',
    options?: RequestOptions,
  ) => {
    memoizedDetail.delete(source, sourceId)
    return request<ComicDetail>(
      `/library/${source}/${sourceId}/replace-path`,
      {
        method: 'POST',
        body: JSON.stringify({
          server_path: serverPath,
          target_chapter: chapterId,
        }),
        signal: options?.signal,
      },
      { timeoutMs: 120000, ...options },
    )
  },
  appendPages: async (
    source: string,
    sourceId: string,
    payload: ComicAppendPayload,
    options?: RequestOptions,
  ) => {
    memoizedDetail.delete(source, sourceId)
    return request<ComicDetail>(
      `/library/${source}/${sourceId}/append`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
        signal: options?.signal,
      },
      { timeoutMs: 120000, ...options },
    )
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
    timeframe: DiscoveryTimeframe = 'week',
    refresh = false,
    options?: RequestOptions,
  ) =>
    request<DiscoveryFeed>(
      '/discovery/ranking',
      { signal: options?.signal },
      {
        ...options,
        params: {
          timeframe,
          refresh: refresh ? 'true' : undefined,
        },
      },
    ),
  imageSearchStatus: (options?: RequestOptions) =>
    request<ImageSearchStatus>('/search/image/status', {
      signal: options?.signal,
    }),
  imageSearch: async (file: File, options?: RequestOptions) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<ImageSearchResultItem[]>(
      '/search/image',
      {
        method: 'POST',
        body: formData,
        signal: options?.signal,
      },
      { timeoutMs: 60000, ...options },
    )
  },
  searchDialogue: (q: string, source?: string, limit: number = 20, options?: RequestOptions) =>
    request<DialogueSearchResponse>(
      '/search/dialogue',
      { signal: options?.signal },
      { ...options, params: { q, source, limit } },
    ),
  getReadingProgress: (source: string, sourceId: string, options?: RequestOptions) =>
    request<ReadingProgressInfo>(`/library/${source}/${sourceId}/progress`, {
      signal: options?.signal,
    }),
  saveReadingProgress: (
    source: string,
    sourceId: string,
    page: number,
    total_pages?: number,
    options?: RequestOptions,
  ) =>
    request<ReadingProgressInfo>(`/library/${source}/${sourceId}/progress`, {
      method: 'PUT',
      body: JSON.stringify({ page, total_pages }),
      signal: options?.signal,
    }),
  getCuratorPasses: (options?: RequestOptions) =>
    request<GuestPass[]>('/curator/passes', {
      signal: options?.signal,
    }),
  createCuratorPass: (payload: CreateGuestPassPayload, options?: RequestOptions) =>
    request<GuestPass>('/curator/passes', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal: options?.signal,
    }),
  updateCuratorPass: (passId: number, payload: UpdateGuestPassPayload, options?: RequestOptions) =>
    request<GuestPass>(`/curator/passes/${passId}`, {
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
  `${BASE}/library/${source}/${sourceId}/pages/${index}/file`

export const pageThumbUrl = (source: string, sourceId: string, index: number) =>
  `${BASE}/library/${source}/${sourceId}/pages/${index}/thumbnail.webp`

export const coverFileUrl = (source: string, sourceId: string, index: number, width?: number) => {
  const base = `${BASE}/library/${source}/${sourceId}/covers/${index}/file.webp`
  const qs = buildQueryString({ w: width })
  return qs ? `${base}?${qs}` : base
}

// T17：章节目录封面端点（后端按章节 id 定位，从该话第一页生成并池化缓存）
export const chapterCoverUrl = (
  source: string,
  sourceId: string,
  chapterId: string,
  width?: number,
) => {
  const base = `${BASE}/library/${source}/${sourceId}/chapters/${chapterId}/cover.webp`
  const qs = buildQueryString({ w: width })
  return qs ? `${base}?${qs}` : base
}

/** 为图片/封面 URL 安全附加宽度参数（?w=360 或 &w=360），自动保护 data:/blob: 协议并更新已有参数 */
export const withWidth = (url: string, width: number): string => {
  if (!url) return ''
  if (url.startsWith('data:') || url.startsWith('blob:')) return url
  try {
    const parsed = new URL(url, 'http://localhost')
    parsed.searchParams.set('w', String(width))
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      return `${parsed.pathname}${parsed.search}`
    }
    return parsed.toString()
  } catch {
    const sep = url.includes('?') ? '&' : '?'
    return `${url}${sep}w=${width}`
  }
}

/** 生成符合 HTML5 规范的响应式封面 srcset 字符串（默认 360w 阶梯 + 720w 高保真原图） */
export const coverSrcset = (url: string, thumbWidth = 360, fullWidth = 720): string => {
  if (!url || url.startsWith('data:') || url.startsWith('blob:')) return ''
  return `${withWidth(url, thumbWidth)} ${thumbWidth}w, ${url} ${fullWidth}w`
}

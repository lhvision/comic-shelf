/**
 * @file http.ts
 * @description 底层 HTTP 传输与拦截器基础设施（HTTP Transport & Signal Composition）。
 *
 * 核心设计：
 * 1. 【令牌与鉴权拦截】：集中管理 LocalStorage Token 与全局 401 / 登录成功事件广播；
 * 2. 【受控超时与原生复合信号 (combineSignals)】：
 *    利用 Baseline 2024 `AbortSignal.any()` 实现超时与外部取消信号的底层无样板合成，
 *    并在请求兑现后立即 `clearTimeout` 释放定时器，杜绝内存泄漏；
 * 3. 【声明式 URL 查询参数组装 (buildQueryString)】：
 *    纯函数过滤 `undefined`、`null` 与空白字符串，支持数组转逗号字符串。
 */

import { useMemoize } from '@vueuse/core'
import { promiseTry } from '@/utils/promise'
import type { ComicDetail, ProviderInfo } from '@/types'

export const BASE = '/api'
const TOKEN_STORAGE_KEY = 'comic-shelf:auth-token'

/**
 * 从本地存储读取当前鉴权 Token
 */
export function getStoredToken(): string {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

/**
 * 设置或清理本地存储的鉴权 Token
 */
export function setStoredToken(token: string): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // 忽略私密模式下的存储异常
  }
}

export type UnauthorizedHandler = () => void | Promise<void>
const unauthorizedHandlers = new Set<UnauthorizedHandler>()

/**
 * 注册全局 401 未授权回调监听
 */
export function onUnauthorized(handler: UnauthorizedHandler): () => void {
  unauthorizedHandlers.add(handler)
  return () => unauthorizedHandlers.delete(handler)
}

/**
 * 广播 401 未授权事件
 */
export function notifyUnauthorized(): void {
  for (const handler of unauthorizedHandlers) {
    promiseTry(handler).catch(() => {})
  }
}

export type AuthSuccessHandler = () => void | Promise<void>
const authSuccessHandlers = new Set<AuthSuccessHandler>()

/**
 * 注册登录成功全局回调监听
 */
export function onAuthSuccess(handler: AuthSuccessHandler): () => void {
  authSuccessHandlers.add(handler)
  return () => authSuccessHandlers.delete(handler)
}

export type QueryParamValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryParamValue | QueryParamValue[]>

/**
 * 统一请求选项配置
 */
export interface RequestOptions {
  /** 外部主动取消信号 */
  signal?: AbortSignal
  /** 是否跳过本地内存缓存（如详情页强制刷新） */
  bypassCache?: boolean
  /** 超时毫秒数（默认 15000ms） */
  timeoutMs?: number
  /** URL 查询参数字典 */
  params?: QueryParams
}

/**
 * 统一 API 业务异常类
 */
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
 * 1. 超时控制采用 `AbortController` + `clearTimeout(timer)` 可控生命周期；
 * 2. 信号合成采用原生 Baseline 2024 `AbortSignal.any()`，消除手动监听样板代码；
 * 3. 旧版环境自动降级至安全一次性事件监听兜底。
 */
export function combineSignals(
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
 * 纯函数：声明式过滤对象中的 undefined、null、空字符串与空白字符串，
 * 将数组展开为逗号分隔字符串，生成符合规范的 URL 查询字符串。
 */
export function buildQueryString(params?: QueryParams): string {
  if (!params) return ''
  const entries: [string, string][] = []
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === null || val === '') continue
    if (Array.isArray(val)) {
      const filtered = val
        .map((item) => (item !== undefined && item !== null ? String(item).trim() : ''))
        .filter(Boolean)
      if (filtered.length > 0) {
        entries.push([key, filtered.join(',')])
      }
    } else {
      const str = String(val).trim()
      if (str !== '') {
        entries.push([key, str])
      }
    }
  }
  if (entries.length === 0) return ''
  return new URLSearchParams(entries).toString()
}

/**
 * 发送标准 HTTP 请求并执行 JSON 解析与错误处理
 */
export async function request<T>(
  path: string,
  init?: RequestInit,
  options?: RequestOptions,
): Promise<T> {
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

/**
 * 漫画详情内存级 Memoize 缓存
 */
export const memoizedDetail = useMemoize(
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

/**
 * 默认图源列表配置
 */
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

/**
 * Provider 信息列表内存级 Memoize 缓存
 */
export const memoizedProviders = useMemoize(
  async (options?: RequestOptions): Promise<ProviderInfo[]> => {
    try {
      return await request<ProviderInfo[]>('/providers', {
        signal: options?.signal,
      })
    } catch (e) {
      memoizedProviders.clear()
      throw e
    }
  },
)

/**
 * 清除漫画详情内存缓存
 */
export function clearApiDetailCache(source?: string, sourceId?: string): void {
  if (source && sourceId) {
    memoizedDetail.delete(source, sourceId)
  } else {
    memoizedDetail.clear()
  }
}

/**
 * 清除全量客户端内存缓存
 */
export function clearApiCaches(): void {
  clearApiDetailCache()
  memoizedProviders.clear()
}

/**
 * 触发登录成功广播并清空失效缓存
 */
export function notifyAuthSuccess(): void {
  clearApiCaches()
  for (const handler of authSuccessHandlers) {
    promiseTry(handler).catch(() => {})
  }
}

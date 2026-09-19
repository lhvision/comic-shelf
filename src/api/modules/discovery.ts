/**
 * @file discovery.ts
 * @description 官方榜单与作品发现 API 模块（Discovery & Trending Feed Module）。
 *
 * 职责：
 * 1. 查询官方日榜、周榜、月榜热门漫画推荐；
 * 2. 支持强制刷新缓存获取最新排行动态。
 */

import { BASE, buildQueryString, getStoredToken, request, type RequestOptions } from '../core/http'
import type { DiscoveryFeed, DiscoveryTimeframe } from '@/types'

/**
 * 获取官方发现排行榜数据（支持禁漫、哔咔以及日榜、周榜、月榜）
 *
 * @param source 图源模块（'jm' | 'picacg'，默认 'jm'）
 * @param timeframe 时间维度（'day' | 'week' | 'month'，默认 'week'）
 * @param refresh 是否强制穿透缓存请求远端最新数据（默认 false）
 * @param options 可选的请求配置
 * @returns 包含榜单作品列表与更新时间的 DiscoveryFeed 对象
 */
export async function discoveryRanking(
  timeframe?: DiscoveryTimeframe,
  refresh?: boolean,
  options?: RequestOptions,
): Promise<DiscoveryFeed>
export async function discoveryRanking(
  source: 'jm' | 'picacg',
  timeframe?: DiscoveryTimeframe,
  refresh?: boolean,
  options?: RequestOptions,
): Promise<DiscoveryFeed>
export async function discoveryRanking(
  arg1?: 'jm' | 'picacg' | DiscoveryTimeframe,
  arg2?: DiscoveryTimeframe | boolean,
  arg3?: boolean | RequestOptions,
  arg4?: RequestOptions,
): Promise<DiscoveryFeed> {
  let source: 'jm' | 'picacg' | undefined
  let timeframe: DiscoveryTimeframe = 'week'
  let refresh = false
  let options: RequestOptions | undefined

  if (arg1 === 'jm' || arg1 === 'picacg') {
    source = arg1
    if (arg2 === 'week' || arg2 === 'month' || arg2 === 'day') timeframe = arg2
    if (typeof arg3 === 'boolean') refresh = arg3
    if (typeof arg4 === 'object' && arg4 !== null) options = arg4
  } else {
    if (arg1 === 'week' || arg1 === 'month' || arg1 === 'day') timeframe = arg1
    if (typeof arg2 === 'boolean') refresh = arg2
    if (typeof arg3 === 'object' && arg3 !== null) options = arg3 as RequestOptions
  }

  return request<DiscoveryFeed>(
    '/discovery/ranking',
    { signal: options?.signal },
    {
      ...options,
      params: {
        source,
        timeframe,
        refresh: refresh ? 'true' : undefined,
      },
    },
  )
}

/**
 * 构造发现页作品封面直连 URL（内存代理，按需加载，零磁盘占用）
 *
 * @param source 图源平台标识（如 'jm' | 'picacg'）
 * @param sourceId 图源作品唯一 ID
 * @param coverUrl 可选的远端封面原图地址（若提供则直接传递避免后端重复检索）
 * @returns 代理访问 URL
 */
export function discoveryCoverUrl(source: string, sourceId: string, coverUrl?: string): string {
  const token = getStoredToken()
  const qs = buildQueryString({
    source,
    source_id: sourceId,
    cover_url: coverUrl || undefined,
    token: token || undefined,
  })
  return `${BASE}/discovery/cover?${qs}`
}

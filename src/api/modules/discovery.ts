/**
 * @file discovery.ts
 * @description 官方榜单与作品发现 API 模块（Discovery & Trending Feed Module）。
 *
 * 职责：
 * 1. 查询官方日榜、周榜、月榜热门漫画推荐；
 * 2. 支持强制刷新缓存获取最新排行动态。
 */

import { request, type RequestOptions } from '../core/http'
import type { DiscoveryFeed, DiscoveryTimeframe } from '@/types'

/**
 * 获取官方发现排行榜数据（支持日榜、周榜、月榜）
 *
 * @param timeframe 时间维度（'day' | 'week' | 'month'，默认 'week'）
 * @param refresh 是否强制穿透缓存请求远端最新数据（默认 false）
 * @param options 可选的请求配置
 * @returns 包含榜单作品列表与更新时间的 DiscoveryFeed 对象
 */
export async function discoveryRanking(
  timeframe: DiscoveryTimeframe = 'week',
  refresh = false,
  options?: RequestOptions,
): Promise<DiscoveryFeed> {
  return request<DiscoveryFeed>(
    '/discovery/ranking',
    { signal: options?.signal },
    {
      ...options,
      params: {
        timeframe,
        refresh: refresh ? 'true' : undefined,
      },
    },
  )
}

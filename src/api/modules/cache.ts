/**
 * @file cache.ts
 * @description 离线缓存、下载并发控制与访客隐私配置 API 模块（Cache & Download Module）。
 *
 * 职责：
 * 1. 触发全本或单章节后台离线解密下载；
 * 2. 轮询/查询缓存进度与后台下载任务状态（Cache Jobs）；
 * 3. 获取与调整下载并发限制；
 * 4. 获取与配置访客隐私可见性策略。
 */

import { memoizedDetail, request, type RequestOptions } from '../core/http'
import type { CacheJob, CacheProgress, DownloadConcurrency, GuestPrivacySettings } from '@/types'

/**
 * 触发指定作品的全本后台离线缓存下载
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @returns 当前作品缓存进度快照
 */
export async function cacheAll(source: string, sourceId: string): Promise<CacheProgress> {
  memoizedDetail.delete(source, sourceId)
  return request<CacheProgress>(`/library/${source}/${sourceId}/cache`, {
    method: 'POST',
    body: '{}',
  })
}

/**
 * 查询指定作品的全本离线缓存进度
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param options 可选的请求配置
 * @returns 当前作品缓存进度对象
 */
export async function cacheProgress(
  source: string,
  sourceId: string,
  options?: RequestOptions,
): Promise<CacheProgress> {
  return request<CacheProgress>(`/library/${source}/${sourceId}/cache`, {
    signal: options?.signal,
  })
}

/**
 * 查询指定单章节的离线缓存进度
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param chapterId 章节 ID
 * @param options 可选的请求配置
 * @returns 该章节缓存进度对象
 */
export async function chapterCacheProgress(
  source: string,
  sourceId: string,
  chapterId: string,
  options?: RequestOptions,
): Promise<CacheProgress> {
  return request<CacheProgress>(`/library/${source}/${sourceId}/chapters/${chapterId}/cache`, {
    signal: options?.signal,
  })
}

/**
 * 触发指定单章节的后台离线下载与解密
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param chapterId 章节 ID
 * @param options 可选的请求配置
 * @returns 章节缓存进度响应
 */
export async function cacheChapter(
  source: string,
  sourceId: string,
  chapterId: string,
  options?: RequestOptions,
): Promise<CacheProgress> {
  memoizedDetail.delete(source, sourceId)
  return request<CacheProgress>(`/library/${source}/${sourceId}/chapters/${chapterId}/cache`, {
    method: 'POST',
    signal: options?.signal,
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  })
}

/**
 * 查询指定作品当前关联的下载任务详情
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param options 可选的请求配置
 * @returns 下载任务详情或状态
 */
export async function cacheJob(
  source: string,
  sourceId: string,
  options?: RequestOptions,
): Promise<CacheJob> {
  return request<CacheJob>(`/library/${source}/${sourceId}/cache/job`, {
    signal: options?.signal,
  })
}

/**
 * 查询全站所有正在运行或排队的后台下载任务列表
 *
 * @param options 可选的请求配置
 * @returns 下载任务数组
 */
export async function cacheJobs(options?: RequestOptions): Promise<CacheJob[]> {
  return request<CacheJob[]>('/cache/jobs', {
    signal: options?.signal,
  })
}

/**
 * 获取当前的全局图片下载并发限制
 *
 * @param options 可选的请求配置
 * @returns 下载并发配置对象
 */
export async function downloadConcurrency(options?: RequestOptions): Promise<DownloadConcurrency> {
  return request<DownloadConcurrency>('/settings/download-concurrency', {
    signal: options?.signal,
  })
}

/**
 * 调整全局图片下载并发限制
 *
 * @param limit 期望的最大并发数（如 1 ~ 8）
 * @returns 更新后的下载并发配置
 */
export async function setDownloadConcurrency(limit: number): Promise<DownloadConcurrency> {
  return request<DownloadConcurrency>('/settings/download-concurrency', {
    method: 'PUT',
    body: JSON.stringify({ limit }),
  })
}

/**
 * 获取访客隐私可见性策略（如是否隐藏新入库未审核漫画）
 *
 * @param options 可选的请求配置
 * @returns 访客隐私配置
 */
export async function guestPrivacy(options?: RequestOptions): Promise<GuestPrivacySettings> {
  return request<GuestPrivacySettings>('/settings/guest-privacy', {
    signal: options?.signal,
  })
}

/**
 * 设置访客隐私可见性策略
 *
 * @param guest_hide_new_comics 是否对访客隐藏新导入漫画
 * @returns 更新后的访客隐私配置
 */
export async function setGuestPrivacy(
  guest_hide_new_comics: boolean,
): Promise<GuestPrivacySettings> {
  return request<GuestPrivacySettings>('/settings/guest-privacy', {
    method: 'PUT',
    body: JSON.stringify({ guest_hide_new_comics }),
  })
}

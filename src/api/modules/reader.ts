/**
 * @file reader.ts
 * @description 阅读器进度同步与历史记录 API 模块（Reader Progress Module）。
 *
 * 职责：
 * 1. 查询作品的最新阅读全局页码与进度状态；
 * 2. 实时/离线同步更新已读页码与总页数。
 */

import { request, type RequestOptions } from '../core/http'
import type { ReadingProgressInfo } from '@/types'

/**
 * 获取指定作品的最新阅读进度
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param options 可选的请求配置
 * @returns 阅读进度信息（含 page, total_pages, updated_at 等）
 */
export async function getReadingProgress(
  source: string,
  sourceId: string,
  options?: RequestOptions,
): Promise<ReadingProgressInfo> {
  return request<ReadingProgressInfo>(`/library/${source}/${sourceId}/progress`, {
    signal: options?.signal,
  })
}

/**
 * 提交并更新指定作品的阅读进度（按全局拍平页码）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param page 当前阅读到的全局页码（1-indexed）
 * @param total_pages 可选的作品总页数
 * @param options 可选的请求配置
 * @returns 更新后的阅读进度信息
 */
export async function saveReadingProgress(
  source: string,
  sourceId: string,
  page: number,
  total_pages?: number,
  options?: RequestOptions,
): Promise<ReadingProgressInfo> {
  return request<ReadingProgressInfo>(`/library/${source}/${sourceId}/progress`, {
    method: 'PUT',
    body: JSON.stringify({ page, total_pages }),
    signal: options?.signal,
  })
}

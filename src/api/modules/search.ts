/**
 * @file search.ts
 * @description 视觉搜图与台词全文检索 API 模块（Image & Dialogue Search Module）。
 *
 * 职责：
 * 1. 查询以图搜图（Image Search Sidecar）引擎状态与索引进度；
 * 2. 上传截图进行本地向量特征比对与精准画页召回；
 * 3. 基于 SQLite FTS5 对全库漫画 OCR 台词/字幕进行高效全文检索与匹配高亮。
 */

import { request, type RequestOptions } from '../core/http'
import type { DialogueSearchResponse, ImageSearchResultItem, ImageSearchStatus } from '@/types'

/**
 * 查询以图搜图服务引擎（Sidecar）的就绪状态与特征索引总量
 *
 * @param options 可选的请求配置
 * @returns 搜图引擎状态对象（如 ready, indexed_count 等）
 */
export async function imageSearchStatus(options?: RequestOptions): Promise<ImageSearchStatus> {
  return request<ImageSearchStatus>('/search/image/status', {
    signal: options?.signal,
  })
}

/**
 * 上传图片文件进行以图搜图，检索书架中相似度最高的漫画画页
 *
 * @param file 待检索的图片文件
 * @param options 可选的请求配置
 * @returns 命中画页列表，包含相似度得分、对应作品与全局页码
 */
export async function imageSearch(
  file: File,
  options?: RequestOptions,
): Promise<ImageSearchResultItem[]> {
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
}

/**
 * 基于 SQLite FTS5 对全库漫画台词进行精准/分词全文检索
 *
 * @param q 搜索关键词或台词短语
 * @param source 可选限定特定图源
 * @param limit 返回的最大结果条数（默认 20）
 * @param options 可选的请求配置
 * @returns 命中的台词列表及关联作品/页码信息
 */
export async function searchDialogue(
  q: string,
  source?: string,
  limit = 20,
  options?: RequestOptions,
): Promise<DialogueSearchResponse> {
  return request<DialogueSearchResponse>(
    '/search/dialogue',
    { signal: options?.signal },
    { ...options, params: { q, source, limit } },
  )
}

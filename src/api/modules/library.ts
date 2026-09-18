/**
 * @file library.ts
 * @description 书架资产与核心漫画管理领域 API 模块（Library & Comic Asset Module）。
 *
 * 职责：
 * 1. 提供支持的多图源 Provider 列表查询与缓存；
 * 2. 多维度筛选与分页检索书架漫画资产；
 * 3. 获取书架聚类 Facets（总数、在读、已读、收藏及高频标签分布）；
 * 4. 作品详情获取（具备内存级 useMemoize 缓存与主动失效机制）；
 * 5. 远端作品导入、作品删除、收藏状态切换与元数据编辑。
 */

import { memoizedDetail, memoizedProviders, request, type RequestOptions } from '../core/http'
import type {
  ComicDetail,
  ImportRequest,
  ImportResult,
  LibraryFacetsResponse,
  LibraryPageResponse,
  LibraryQueryParams,
  MetadataUpdatePayload,
  ProviderInfo,
} from '@/types'

/**
 * 获取支持的漫画图源 Provider 清单（采用内存级 memoize 缓存）
 *
 * @param options 可选的请求配置
 * @returns 支持的 Provider 列表（含 jm, picacg, local 等）
 */
export async function providers(options?: RequestOptions): Promise<ProviderInfo[]> {
  return memoizedProviders(options)
}

/**
 * 多维度分页检索与筛选书架中的漫画作品
 *
 * @param params 检索条件（含关键词、标签、图源、阅读状态、排序等）
 * @param options 可选的请求配置
 * @returns 分页响应，包含漫画列表、总数及是否有下一页
 */
export async function library(
  params?: LibraryQueryParams,
  options?: RequestOptions,
): Promise<LibraryPageResponse> {
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
}

/**
 * 获取书架的聚合统计数据（Facets）
 *
 * @param source 可选按特定图源过滤
 * @param options 可选的请求配置
 * @returns 统计数据（含 total, reading, completed, favorites 及 tags 列表）
 */
export async function libraryFacets(
  source?: string,
  options?: RequestOptions,
): Promise<LibraryFacetsResponse> {
  return request<LibraryFacetsResponse>(
    '/library/facets',
    { signal: options?.signal },
    { ...options, params: { source } },
  )
}

/**
 * 获取指定作品的完整结构化详情数据（带内存缓存与 bypassCache 支持）
 *
 * @param source 图源平台标识（如 'jm' | 'picacg' | 'local'）
 * @param sourceId 作品 ID
 * @param options 可选的请求配置；若 `options.bypassCache` 为 true，则强制清空当前条目缓存后重拉
 * @returns 作品详情对象（包含元数据、章节列表及全局画页拍平索引）
 */
export async function detail(
  source: string,
  sourceId: string,
  options?: RequestOptions,
): Promise<ComicDetail> {
  if (options?.bypassCache) {
    memoizedDetail.delete(source, sourceId)
  }
  return memoizedDetail(source, sourceId, options)
}

/**
 * 向书架导入远端作品（异步入库，触发详情缓存全量清空）
 *
 * @param payload 导入请求载荷（含 source, source_id 等）
 * @returns 导入结果响应
 */
export async function importComic(payload: ImportRequest): Promise<ImportResult> {
  memoizedDetail.clear()
  return request<ImportResult>('/library/import', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * 从书架中永久删除指定作品（清除该作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @returns 操作结果 `{ ok: boolean }`
 */
export async function deleteComic(source: string, sourceId: string): Promise<{ ok: boolean }> {
  memoizedDetail.delete(source, sourceId)
  return request<{ ok: boolean }>(`/library/${source}/${sourceId}`, {
    method: 'DELETE',
  })
}

/**
 * 切换指定作品的收藏状态（清除该作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param favorite 目标收藏状态（true 收藏，false 取消）
 * @returns 更新后的收藏状态
 */
export async function setFavorite(
  source: string,
  sourceId: string,
  favorite: boolean,
): Promise<{ ok: boolean; favorite: boolean }> {
  memoizedDetail.delete(source, sourceId)
  return request<{ ok: boolean; favorite: boolean }>(`/library/${source}/${sourceId}/favorite`, {
    method: 'PATCH',
    body: JSON.stringify({ favorite }),
  })
}

/**
 * 更新作品元数据（如标题、作者、标签等自定义信息，并清除详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param payload 待更新的元数据载荷
 * @returns 更新后的完整作品详情
 */
export async function updateMetadata(
  source: string,
  sourceId: string,
  payload: MetadataUpdatePayload,
): Promise<ComicDetail> {
  memoizedDetail.delete(source, sourceId)
  return request<ComicDetail>(`/library/${source}/${sourceId}/metadata`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

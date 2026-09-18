/**
 * @file workshop.ts
 * @description 本地工坊、PDF 嗅探与切分、章节管理与画页上传 API 模块（Workshop & Chapter Studio Module）。
 *
 * 职责：
 * 1. 本地画集新建、服务器本地路径导入（Local Path Import）；
 * 2. PDF 文件临时暂存嗅探与智能切分入库；
 * 3. 画页上传、批量替换、追加合并；
 * 4. 章节元数据重命名与单话删除。
 */

import { memoizedDetail, request, type RequestOptions } from '../core/http'
import type {
  ComicAppendPayload,
  ComicDetail,
  CreateFromStagedPdfPayload,
  LocalComicCreatePayload,
  LocalPathImportPayload,
  PdfInspectResponse,
} from '@/types'

/**
 * 在本地自建库中创建全新漫画作品（清空详情缓存）
 *
 * @param payload 本地漫画创建载荷（标题、作者、封面等）
 * @param options 可选的请求配置
 * @returns 创建成功的作品详情
 */
export async function createLocalComic(
  payload: LocalComicCreatePayload,
  options?: RequestOptions,
): Promise<ComicDetail> {
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
}

/**
 * 从服务器本地路径导入漫画文件夹或归档（清空详情缓存）
 *
 * @param payload 服务器路径导入载荷
 * @param options 可选的请求配置
 * @returns 导入成功的作品详情
 */
export async function importLocalPath(
  payload: LocalPathImportPayload,
  options?: RequestOptions,
): Promise<ComicDetail> {
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
}

/**
 * 上传并嗅探 PDF 文件结构（页数、目录树与分卷预估）
 *
 * @param formData 包含 PDF 文件的 FormData 表单
 * @param options 可选的请求配置
 * @returns PDF 嗅探分析结果，包含 staging_token 与章节建议
 */
export async function inspectPdf(
  formData: FormData,
  options?: RequestOptions,
): Promise<PdfInspectResponse> {
  return request<PdfInspectResponse>(
    '/library/local/inspect-pdf',
    {
      method: 'POST',
      body: formData,
      signal: options?.signal,
    },
    { timeoutMs: 180000, ...options },
  )
}

/**
 * 删除服务器暂存的 PDF 临时文件
 *
 * @param stagingToken PDF 暂存凭证 Token
 * @param options 可选的请求配置
 * @returns 操作结果 `{ ok: boolean }`
 */
export async function deleteStagedPdf(
  stagingToken: string,
  options?: RequestOptions,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/library/local/staged-pdf/${encodeURIComponent(stagingToken)}`,
    {
      method: 'DELETE',
      signal: options?.signal,
    },
    options,
  )
}

/**
 * 基于已暂存的 PDF 执行切分渲染并入库为本地画集（清空详情缓存）
 *
 * @param payload 包含 staging_token 与切分规则的载荷
 * @param options 可选的请求配置
 * @returns 生成的作品详情
 */
export async function createFromStagedPdf(
  payload: CreateFromStagedPdfPayload,
  options?: RequestOptions,
): Promise<ComicDetail> {
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
}

/**
 * 向作品或指定章节上传并插入多张画页（清除作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param files 待上传的图片文件列表
 * @param chapterId 可选的目标章节 ID
 * @param newChapterTitle 若新建章节，指定新章节标题
 * @param options 可选的请求配置
 * @returns 更新后的作品详情
 */
export async function uploadPages(
  source: string,
  sourceId: string,
  files: File[],
  chapterId = '',
  newChapterTitle = '',
  options?: RequestOptions,
): Promise<ComicDetail> {
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
}

/**
 * 使用上传的图片列表整话/整本覆盖替换画页（清除作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param files 替换的图片文件列表
 * @param chapterId 可选的目标章节 ID
 * @param options 可选的请求配置
 * @returns 更新后的作品详情
 */
export async function replaceComicPages(
  source: string,
  sourceId: string,
  files: File[],
  chapterId = '',
  options?: RequestOptions,
): Promise<ComicDetail> {
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
}

/**
 * 从服务器本地路径重新加载并替换画页（清除作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param serverPath 服务器绝对路径
 * @param chapterId 可选的目标章节 ID
 * @param options 可选的请求配置
 * @returns 更新后的作品详情
 */
export async function replaceComicPagesFromPath(
  source: string,
  sourceId: string,
  serverPath: string,
  chapterId = '',
  options?: RequestOptions,
): Promise<ComicDetail> {
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
}

/**
 * 追加画页或合并其他画集内容（清除作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param payload 追加载荷
 * @param options 可选的请求配置
 * @returns 更新后的作品详情
 */
export async function appendPages(
  source: string,
  sourceId: string,
  payload: ComicAppendPayload,
  options?: RequestOptions,
): Promise<ComicDetail> {
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
}

/**
 * 重命名或修改指定章节标题（清除作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param chapterId 目标章节 ID
 * @param title 新的章节标题
 * @returns 更新后的作品详情
 */
export async function updateChapter(
  source: string,
  sourceId: string,
  chapterId: string,
  title: string,
): Promise<ComicDetail> {
  memoizedDetail.delete(source, sourceId)
  return request<ComicDetail>(
    `/library/${source}/${sourceId}/chapters/${encodeURIComponent(chapterId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    },
  )
}

/**
 * 删除指定作品的某一章节（清除作品详情缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param chapterId 待删除章节 ID
 * @returns 更新后的作品详情
 */
export async function deleteChapter(
  source: string,
  sourceId: string,
  chapterId: string,
): Promise<ComicDetail> {
  memoizedDetail.delete(source, sourceId)
  return request<ComicDetail>(
    `/library/${source}/${sourceId}/chapters/${encodeURIComponent(chapterId)}`,
    {
      method: 'DELETE',
    },
  )
}

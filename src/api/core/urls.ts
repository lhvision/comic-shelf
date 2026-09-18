/**
 * @file urls.ts
 * @description 媒体资源、缩略图与响应式封面 URL 辅助函数（Asset URL Builders）。
 *
 * 核心设计：
 * 1. 【安全与协议保留】：对于 `data:` 与 `blob:` 协议自动豁免，避免 URL 重写导致资源损坏；
 * 2. 【响应式与尺寸降级】：利用 `withWidth` 为媒体路径安全附加宽度查询参数，并生成标准 HTML5 `srcset` 阶梯；
 * 3. 【章节封面定位】：为多章节画集提供基于章节 ID 的动态池化封面端点 URL。
 */

import { BASE, buildQueryString } from './http'

/**
 * 获取指定漫画画页的高清原图文件 URL
 *
 * @param source 图源平台标识（如 'jm' | 'picacg' | 'local'）
 * @param sourceId 图源作品唯一 ID
 * @param index 全局画页序号（1-indexed）
 * @returns 完整文件访问路径（如 `/api/library/jm/12345/pages/1/file`）
 */
export const pageFileUrl = (source: string, sourceId: string, index: number): string =>
  `${BASE}/library/${source}/${sourceId}/pages/${index}/file`

/**
 * 获取指定漫画画页的 WebP 压缩缩略图 URL
 *
 * @param source 图源平台标识（如 'jm' | 'picacg' | 'local'）
 * @param sourceId 图源作品唯一 ID
 * @param index 全局画页序号（1-indexed）
 * @returns 缩略图访问路径（如 `/api/library/jm/12345/pages/1/thumbnail.webp`）
 */
export const pageThumbUrl = (source: string, sourceId: string, index: number): string =>
  `${BASE}/library/${source}/${sourceId}/pages/${index}/thumbnail.webp`

/**
 * 获取指定作品封面的 WebP URL（支持指定缩放宽度）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param index 封面序号（通常为 1）
 * @param width 可选的期望像素宽度（如 360, 720）
 * @returns 封面 URL，若指定了 width 则附加 `?w={width}` 查询参数
 */
export const coverFileUrl = (
  source: string,
  sourceId: string,
  index: number,
  width?: number,
): string => {
  const base = `${BASE}/library/${source}/${sourceId}/covers/${index}/file.webp`
  const qs = buildQueryString({ w: width })
  return qs ? `${base}?${qs}` : base
}

/**
 * 获取指定章节的专属封面 WebP URL（从该章节第一页生成并池化缓存）
 *
 * @param source 图源平台标识
 * @param sourceId 作品 ID
 * @param chapterId 章节 ID
 * @param width 可选的期望像素宽度
 * @returns 章节封面 URL
 */
export const chapterCoverUrl = (
  source: string,
  sourceId: string,
  chapterId: string,
  width?: number,
): string => {
  const base = `${BASE}/library/${source}/${sourceId}/chapters/${chapterId}/cover.webp`
  const qs = buildQueryString({ w: width })
  return qs ? `${base}?${qs}` : base
}

/**
 * 为图片/封面 URL 安全附加或更新宽度参数（如 `?w=360` 或 `&w=360`）
 *
 * @description 自动识别并保留 `data:` / `blob:` 协议；若 URL 已有 query 参数则安全更新。
 * @param url 目标图片 URL
 * @param width 目标像素宽度
 * @returns 包含宽度参数的 URL
 */
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

/**
 * 生成符合 HTML5 规范的响应式封面 srcset 字符串（默认 360w 阶梯 + 720w 高保真原图）
 *
 * @param url 基础封面 URL
 * @param thumbWidth 缩略图阶梯宽度（默认 360）
 * @param fullWidth 原图/高保真阶梯宽度（默认 720）
 * @returns 标准 srcset 字符串，如 `/api/.../cover.webp?w=360 360w, /api/.../cover.webp 720w`
 */
export const coverSrcset = (url: string, thumbWidth = 360, fullWidth = 720): string => {
  if (!url || url.startsWith('data:') || url.startsWith('blob:')) return ''
  return `${withWidth(url, thumbWidth)} ${thumbWidth}w, ${url} ${fullWidth}w`
}

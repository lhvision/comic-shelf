/**
 * @file format.ts
 * @description 纸间全站数据大小与文本呈现格式化工具集。
 */

/**
 * 本地收录成功提示：标题 + 车号印章；有页数时附带页数。
 * 网页上传刚建档时 `page_count` 可能仍为 0，此时不谎报页数。
 *
 * @param meta 刚收录作品的标题、车号与页数
 * @param kindLabel 可选品类前缀，如 `PDF 漫画`
 * @returns 如 `已收录 PDF 漫画《缇雅拆帧》（LOC_tiya-frames，共 12 页）`
 */
export function formatLocalImportToast(
  meta: {
    title: string
    display_id: string
    page_count: number
  },
  kindLabel?: string,
): string {
  const pages = meta.page_count > 0 ? `，共 ${meta.page_count} 页` : ''
  const kind = kindLabel?.trim() ? ` ${kindLabel.trim()}` : ''
  return `已收录${kind}《${meta.title}》（${meta.display_id}${pages}）`
}

/**
 * 格式化字节大小为人类可读格式（如 "512 B"、"1.0 KB"、"3.4 MB"、"4.5 GB"）。
 *
 * @param bytes 字节数
 * @returns 格式化后的带单位文本
 */
export function formatBytes(bytes: number): string {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), units.length - 1)
  const val = bytes / k ** i
  return `${val < 10 && i > 0 ? val.toFixed(1) : Math.round(val)} ${units[i]}`
}

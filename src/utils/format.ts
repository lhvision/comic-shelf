/**
 * @file format.ts
 * @description 纸间全站数据大小与文本呈现格式化工具集（含本地收录成功提示文案）。
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

/**
 * 将各类日期输入（ISO 8601 字符串、秒/毫秒时间戳、带空格服务端历史时间串）解析为 UTC 毫秒时间戳。
 *
 * @param val 日期字符串、数字时间戳或 null/undefined
 * @returns 毫秒时间戳，解析失败返回 0
 */
export function parseDateToMs(val: string | number | null | undefined): number {
  if (!val) return 0
  if (typeof val === 'number') {
    if (!Number.isFinite(val) || val <= 0) return 0
    return val < 1e11 ? val * 1000 : val
  }
  const trimmed = val.trim()
  if (!trimmed) return 0

  if (/^\d+$/.test(trimmed)) {
    const num = Number.parseInt(trimmed, 10)
    return num < 1e11 ? num * 1000 : num
  }

  let ms = Date.parse(trimmed)
  if (Number.isNaN(ms) || /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$/.test(trimmed)) {
    const isoCandidate = trimmed.replace(' ', 'T') + 'Z'
    const parsed = Date.parse(isoCandidate)
    if (!Number.isNaN(parsed)) {
      ms = parsed
    }
  }

  return Number.isNaN(ms) ? 0 : ms
}

/**
 * 格式化时间为本地客户端可读的年月日时分秒（如 "2026-10-17 16:48:31"）。
 *
 * @param val 日期输入（ISO 串、时间戳或 Date）
 * @returns 格式化后的本地时间字符串，非法输入返回空字符串
 */
export function formatDateTime(val: string | number | Date | null | undefined): string {
  if (!val) return ''
  const ms = val instanceof Date ? val.getTime() : parseDateToMs(val)
  if (!ms) return ''
  const date = new Date(ms)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
}

/**
 * 格式化时间为相对于当前客户端时间的人性化描述（如 "刚刚"、"5 分钟前"、"2 小时前"）。
 *
 * @param val 日期输入（ISO 串、时间戳或 Date）
 * @returns 相对时间文本
 */
export function formatRelativeTime(val: string | number | Date | null | undefined): string {
  if (!val) return '从未'
  const ms = val instanceof Date ? val.getTime() : parseDateToMs(val)
  if (!ms) return '从未'
  const now = Date.now()
  const diffSec = Math.floor((now - ms) / 1000)

  if (diffSec < 60) return '刚刚'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`
  const days = Math.floor(diffSec / 86400)
  if (days < 30) return `${days} 天前`
  return formatDateTime(ms).slice(0, 10)
}

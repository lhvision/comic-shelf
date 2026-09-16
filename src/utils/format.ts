/**
 * @file format.ts
 * @description 纸间全站数据大小与文本呈现格式化工具集。
 */

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

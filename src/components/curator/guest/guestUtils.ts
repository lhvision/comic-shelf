/**
 * @file guestUtils.ts
 * @description 纸间 · 访客通行证通用辅助函数（时间戳格式化、相对时间计算与密钥脱敏）。
 */

import { formatDateTime, formatRelativeTime as formatRelativeTimeBase } from '@/utils/format'

/**
 * 格式化 Unix 秒级时间戳为本地年月日字符串
 * @param ts 秒级 Unix 时间戳（为空表示永久有效）
 * @returns 格式化后的日期字符串（如 "2026-09-01" 或 "永久有效"）
 */
export function formatTimestamp(ts: number | null): string {
  if (!ts) return '永久有效'
  return formatDateTime(ts).slice(0, 10)
}

/**
 * 格式化时间戳为人类可读的相对时间（如 "刚刚"、"5 分钟前"）
 * @param ts 秒级 Unix 时间戳
 * @returns 相对时间描述
 */
export function formatRelativeTime(ts: number | null): string {
  if (!ts) return '从未'
  return formatRelativeTimeBase(ts)
}

/**
 * 对长通行口令进行中间掩码脱敏展示
 * @param token 完整口令字符串
 * @returns 脱敏后的字符串（如 "a1b2c3••••x8y9z0"）
 */
export function maskToken(token: string): string {
  if (!token || token.length < 12) return token
  return `${token.slice(0, 6)}••••${token.slice(-6)}`
}

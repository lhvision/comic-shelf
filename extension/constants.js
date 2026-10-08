/**
 * 纸间 · Paper Room 浏览器扩展内置常量与工具函数
 */

export const BUILTIN_PROVIDERS = [
  {
    source: 'jm',
    name: '禁漫天堂',
    badge: 'JM',
    domains: [
      '18comic.vip',
      '18comic.ink',
      'jmcomic-zzz.one',
      'jmcomic-zzz.org',
      'comic18j-ada.space',
      'comic18j-ada.online',
      'comic18j-ada.work',
    ],
  },
  {
    source: 'picacg',
    name: '哔咔漫画',
    badge: '哔咔',
    domains: ['manhuapica.com', 'picawang.com'],
  },
  {
    source: 'copymanga',
    name: '拷贝漫画',
    badge: '拷贝',
    domains: ['mangacopy.com', 'copy4000.com'],
  },
]

export const DEFAULT_DOMAINS = BUILTIN_PROVIDERS.flatMap((p) => p.domains)

/**
 * 清理并规范化单个域名字符串
 * 剥离协议头、尾部路径、端口号与前导通配符
 */
export function sanitizeDomain(raw) {
  if (!raw || typeof raw !== 'string') return ''
  return raw
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/[/?#].*$/, '')
    .replace(/^\*+\.?/, '')
    .replace(/:\d+$/, '')
    .toLowerCase()
}

/**
 * 校验域名合法性（支持标准域名、IPv4 或 localhost）
 */
export function isValidDomain(raw) {
  const clean = sanitizeDomain(raw)
  if (!clean || clean.length > 253) return false
  if (clean === 'localhost') return true
  const isIpv4 = /^(\d{1,3}\.){3}\d{1,3}$/.test(clean)
  if (isIpv4) {
    const parts = clean.split('.').map(Number)
    return parts.every((p) => p >= 0 && p <= 255)
  }
  const labels = clean.split('.')
  if (labels.length < 2) return false
  return labels.every(
    (label) =>
      label.length > 0 && label.length <= 63 && /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(label),
  )
}

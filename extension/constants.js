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
 * 创建空图源自定义分流映射字典
 */
export function createEmptyCustomDomainsMap() {
  return {
    jm: [],
    picacg: [],
    copymanga: [],
  }
}

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

/**
 * 启发式猜测域名属于哪个图源（用于输入时智能切换推荐）
 */
export function guessProviderFromDomain(raw) {
  const clean = sanitizeDomain(raw)
  if (!clean) return null
  if (clean.includes('18comic') || clean.includes('jmcomic') || clean.includes('comic18')) {
    return 'jm'
  }
  if (clean.includes('pica') || clean.includes('manhuapica')) {
    return 'picacg'
  }
  if (clean.includes('copymanga') || clean.includes('mangacopy') || clean.includes('copy4000')) {
    return 'copymanga'
  }
  return null
}

/**
 * 查找指定域名是否已被某个图源占用，或与已有域名存在父子域名重叠冲突
 * @param {string} raw
 * @param {Record<string, string[]>} [customMap]
 * @returns {{ source: string, name: string, badge: string, isBuiltin: boolean, conflictType: 'exact' | 'subdomain' | 'parent', conflictDomain: string } | null}
 */
export function findDomainOwner(raw, customMap = {}) {
  const clean = sanitizeDomain(raw)
  if (!clean) return null

  // 辅助检测 candidate 与 target 的冲突关系
  function checkConflict(target) {
    const cleanTarget = sanitizeDomain(target)
    if (!cleanTarget) return null
    if (clean === cleanTarget) {
      return { type: 'exact', domain: cleanTarget }
    }
    if (clean.endsWith(`.${cleanTarget}`)) {
      return { type: 'subdomain', domain: cleanTarget }
    }
    if (cleanTarget.endsWith(`.${clean}`)) {
      return { type: 'parent', domain: cleanTarget }
    }
    return null
  }

  // 1. 优先查系统内置
  for (const provider of BUILTIN_PROVIDERS) {
    for (const d of provider.domains) {
      const conflict = checkConflict(d)
      if (conflict) {
        return {
          source: provider.source,
          name: provider.name,
          badge: provider.badge,
          isBuiltin: true,
          conflictType: conflict.type,
          conflictDomain: conflict.domain,
        }
      }
    }
  }

  // 2. 查自定义字典
  if (customMap && typeof customMap === 'object') {
    for (const provider of BUILTIN_PROVIDERS) {
      const list = customMap[provider.source]
      if (Array.isArray(list)) {
        for (const d of list) {
          const conflict = checkConflict(d)
          if (conflict) {
            return {
              source: provider.source,
              name: provider.name,
              badge: provider.badge,
              isBuiltin: false,
              conflictType: conflict.type,
              conflictDomain: conflict.domain,
            }
          }
        }
      }
    }
  }

  return null
}

/**
 * 将历史存储数据（一维数组或非标对象）平滑迁移为合法的 CustomDomainsMap，
 * 严格剔除内置重复项与跨图源重复项，满足全局唯一性约束。
 */
export function migrateCustomDomains(stored) {
  const result = createEmptyCustomDomainsMap()

  if (Array.isArray(stored)) {
    // 兼容历史一维数组: string[]
    for (const raw of stored) {
      const clean = sanitizeDomain(raw)
      if (!clean || !isValidDomain(clean)) continue
      if (findDomainOwner(clean, result)) continue
      const guessed = guessProviderFromDomain(clean) || 'jm'
      if (result[guessed]) {
        result[guessed].push(clean)
      }
    }
    return result
  }

  if (stored && typeof stored === 'object') {
    for (const provider of BUILTIN_PROVIDERS) {
      const list = stored[provider.source]
      if (Array.isArray(list)) {
        for (const raw of list) {
          const clean = sanitizeDomain(raw)
          if (!clean || !isValidDomain(clean)) continue
          if (findDomainOwner(clean, result)) continue
          result[provider.source].push(clean)
        }
      }
    }
  }

  return result
}

/**
 * 根据主机名查找匹配的图源来源定义（支持二级/子域名向后匹配）
 * @param {string} hostname
 * @param {Record<string, string[]>} [customMap]
 * @returns {{ source: string, name: string, badge: string, matchedDomain: string } | null}
 */
export function matchDomainToProvider(hostname, customMap = {}) {
  if (!hostname || typeof hostname !== 'string') return null
  const lowerHost = hostname.toLowerCase()

  for (const provider of BUILTIN_PROVIDERS) {
    const customList =
      customMap && Array.isArray(customMap[provider.source]) ? customMap[provider.source] : []
    const allDomainsForProvider = [...provider.domains, ...customList]

    for (const d of allDomainsForProvider) {
      const clean = sanitizeDomain(d)
      if (!clean) continue
      if (lowerHost === clean || lowerHost.endsWith(`.${clean}`)) {
        return {
          source: provider.source,
          name: provider.name,
          badge: provider.badge,
          matchedDomain: clean,
        }
      }
    }
  }

  return null
}

/**
 * 获取当前所有已生效的域名列表（内置 + 全图源自定义去重）
 * @param {Record<string, string[]>} [customMap]
 * @returns {string[]}
 */
export function getAllConfiguredDomains(customMap = {}) {
  const custom = customMap && typeof customMap === 'object' ? customMap : {}
  const list = [...DEFAULT_DOMAINS]
  for (const provider of BUILTIN_PROVIDERS) {
    if (Array.isArray(custom[provider.source])) {
      list.push(...custom[provider.source])
    }
  }
  return [...new Set(list.map(sanitizeDomain).filter(Boolean))]
}

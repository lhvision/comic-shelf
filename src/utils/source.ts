/**
 * @file source.ts
 * @description 纸间全站图源元数据字典与映射工具集。
 *
 * 职责：
 * 1. 提供单源真理（SSOT）的图源字典（全称、简称、印章、标识名与原站链接映射）；
 * 2. 替代各组件散落硬编码的三元表达式与局部 Map；
 * 3. 支撑后续无缝接入新图源站点（如 EH / NH / 拷贝等）的统一扩展契约。
 */

export interface SourceMeta {
  /** 图源唯一键名，如 'jm'、'picacg'、'local' */
  key: string
  /** 图源全称，如 '禁漫天堂'、'哔咔漫画'、'本地自建' */
  name: string
  /** 图源简称，如 '禁漫'、'哔咔'、'本地' */
  shortName: string
  /** 图源印章徽印，如 'JM'、'PICA'、'LOCAL' */
  badge: string
  /** 识别号展示前缀，如 '禁漫车号'、'哔咔 ID'、'自建编号' */
  idLabel: string
  /** 原站链接构造函数（可选） */
  externalUrl?: (sourceId: string) => string
}

/**
 * 纸间内置图源静态映射表
 */
export const SOURCE_MAP: Record<string, SourceMeta> = {
  jm: {
    key: 'jm',
    name: '禁漫天堂',
    shortName: '禁漫',
    badge: 'JM',
    idLabel: '禁漫车号',
    externalUrl: (sourceId) => `https://18comic.vip/album/${sourceId}`,
  },
  picacg: {
    key: 'picacg',
    name: '哔咔漫画',
    shortName: '哔咔',
    badge: 'PICA',
    idLabel: '哔咔 ID',
    externalUrl: (sourceId) => `https://picawang.com/comic/${sourceId}`,
  },
  local: {
    key: 'local',
    name: '本地自建',
    shortName: '本地',
    badge: 'LOCAL',
    idLabel: '自建编号',
  },
}

/**
 * 获取指定图源的完整元数据配置；未知图源自动降级生成自适应元数据。
 *
 * @param source 图源 key（如 'jm'、'picacg'）
 * @returns 对应的 SourceMeta 元数据配置对象
 */
export function getSourceMeta(source?: string): SourceMeta {
  if (!source) return SOURCE_MAP.jm!
  const found = SOURCE_MAP[source.toLowerCase()]
  if (found) return found

  const upper = source.toUpperCase()
  return {
    key: source,
    name: upper,
    shortName: upper,
    badge: upper,
    idLabel: `${upper} 编号`,
  }
}

/**
 * 获取图源全称（如 '禁漫天堂'、'哔咔漫画'）。
 */
export function getSourceName(source?: string): string {
  return getSourceMeta(source).name
}

/**
 * 获取图源简称（如 '禁漫'、'哔咔'、'本地'）。
 */
export function getSourceShortName(source?: string): string {
  return getSourceMeta(source).shortName
}

/**
 * 获取图源徽印标签（如 'JM'、'PICA'、'LOCAL'）。
 */
export function getSourceBadge(source?: string): string {
  return getSourceMeta(source).badge
}

/**
 * 获取图源标识号名称（如 '禁漫车号'、'哔咔 ID'、'自建编号'）。
 */
export function getSourceIdLabel(source?: string): string {
  return getSourceMeta(source).idLabel
}

/**
 * 获取图源原站外部直达链接（若该图源不支持则返回 undefined）。
 */
export function getSourceExternalUrl(source?: string, sourceId?: string): string | undefined {
  if (!sourceId) return undefined
  const meta = getSourceMeta(source)
  return meta.externalUrl ? meta.externalUrl(sourceId) : undefined
}

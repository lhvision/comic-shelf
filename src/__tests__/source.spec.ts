/**
 * @file source.spec.ts
 * @description 验证全站图源元数据字典与映射工具集契约。
 */

import { describe, it, expect } from 'vite-plus/test'
import {
  getSourceMeta,
  getSourceName,
  getSourceShortName,
  getSourceBadge,
  getSourceIdLabel,
  getSourceExternalUrl,
  SOURCE_MAP,
} from '@/utils/source'

describe('source utility', () => {
  it('returns well-known metadata for built-in sources', () => {
    expect(getSourceShortName('jm')).toBe('禁漫')
    expect(getSourceName('jm')).toBe('禁漫天堂')
    expect(getSourceBadge('jm')).toBe('JM')
    expect(getSourceIdLabel('jm')).toBe('禁漫车号')

    expect(getSourceShortName('picacg')).toBe('哔咔')
    expect(getSourceName('picacg')).toBe('哔咔漫画')
    expect(getSourceBadge('picacg')).toBe('PICA')
    expect(getSourceIdLabel('picacg')).toBe('哔咔 ID')

    expect(getSourceShortName('local')).toBe('本地')
    expect(getSourceName('local')).toBe('本地自建')
    expect(getSourceBadge('local')).toBe('LOCAL')
    expect(getSourceIdLabel('local')).toBe('自建编号')
  })

  it('handles case-insensitivity correctly', () => {
    expect(getSourceShortName('JM')).toBe('禁漫')
    expect(getSourceShortName('PicAcg')).toBe('哔咔')
    expect(getSourceShortName('LOCAL')).toBe('本地')
  })

  it('generates graceful fallback metadata for future unknown sources', () => {
    const meta = getSourceMeta('ehentai')
    expect(meta.name).toBe('EHENTAI')
    expect(meta.shortName).toBe('EHENTAI')
    expect(meta.badge).toBe('EHENTAI')
    expect(meta.idLabel).toBe('EHENTAI 编号')
  })

  it('defaults to jm when source is omitted or empty', () => {
    expect(getSourceMeta()).toEqual(SOURCE_MAP.jm)
    expect(getSourceMeta('')).toEqual(SOURCE_MAP.jm)
  })

  it('resolves external url correctly for sources supporting external links', () => {
    expect(getSourceExternalUrl('jm', '123456')).toBe('https://18comic.vip/album/123456')
    expect(getSourceExternalUrl('picacg', '6aa41d3bf7e21a74faf94e42')).toBe(
      'https://picawang.com/comic/6aa41d3bf7e21a74faf94e42',
    )
    expect(getSourceExternalUrl('local', 'my_comic')).toBeUndefined()
    expect(getSourceExternalUrl('unknown', '123')).toBeUndefined()
    expect(getSourceExternalUrl('jm', '')).toBeUndefined()
  })
})

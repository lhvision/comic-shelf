import { describe, it, expect } from 'vite-plus/test'
// @ts-expect-error Extension service-worker is vanilla JS without d.ts declarations
import { isSafeUrl, resolveComicInfo, buildUrlPatterns } from '../../extension/service-worker.js'

describe('extension service-worker', () => {
  describe('isSafeUrl', () => {
    it('accepts valid http and https URLs', () => {
      expect(isSafeUrl('http://localhost:8000')).toBe(true)
      expect(isSafeUrl('https://18comic.vip/album/12345')).toBe(true)
    })

    it('rejects unsafe protocols or invalid strings', () => {
      expect(isSafeUrl('javascript:alert(1)')).toBe(false)
      expect(isSafeUrl('data:text/html,<h1>hi</h1>')).toBe(false)
      expect(isSafeUrl('file:///etc/passwd')).toBe(false)
      expect(isSafeUrl('')).toBe(false)
      expect(isSafeUrl(null as unknown as string)).toBe(false)
    })
  })

  describe('resolveComicInfo', () => {
    it('resolves JM comic albums correctly', () => {
      const res = resolveComicInfo('https://18comic.vip/album/123456/title-slug')
      expect(res).toEqual({
        source: 'jm',
        id: '123456',
        name: '禁漫天堂',
      })
    })

    it('refuses JM single chapter photo URLs as direct comic IDs', () => {
      // Photo URLs are individual episode IDs, not album IDs
      const res = resolveComicInfo('https://18comic.vip/photo/123456')
      expect(res).toBeNull()
    })

    it('resolves Picacg web sharing URLs', () => {
      const res = resolveComicInfo(
        'https://picawang.com/comic/5ebe89bf89196b0559e21bf4?from=search',
      )
      expect(res).toEqual({
        source: 'picacg',
        id: '5ebe89bf89196b0559e21bf4',
        name: '哔咔漫画',
      })
    })

    it('resolves CopyManga comic URLs', () => {
      const res = resolveComicInfo(
        'https://mangacopy.com/comic/xiangyaochengweiyingzhishilizhe/chapter/1',
      )
      expect(res).toEqual({
        source: 'copymanga',
        id: 'xiangyaochengweiyingzhishilizhe',
        name: '拷贝漫画',
      })
    })

    it('returns null for unrelated sites or unparseable URLs', () => {
      expect(resolveComicInfo('https://google.com')).toBeNull()
      expect(resolveComicInfo('https://github.com/torvalds/linux')).toBeNull()
      expect(resolveComicInfo('not-a-url')).toBeNull()
    })
  })

  describe('buildUrlPatterns', () => {
    it('generates wildcard pattern for standard hostnames', () => {
      const patterns = buildUrlPatterns(['18comic.vip', 'mangacopy.com'])
      expect(patterns).toContain('*://*.18comic.vip/*')
      expect(patterns).toContain('*://*.mangacopy.com/*')
    })

    it('strips leading wildcards, protocols, paths, and ports', () => {
      const patterns = buildUrlPatterns([
        '*.18comic.vip',
        'https://copymanga.com/comic/123',
        'jmcomic.me:443',
      ])
      expect(patterns).toEqual([
        '*://*.18comic.vip/*',
        '*://*.copymanga.com/*',
        '*://*.jmcomic.me/*',
      ])
    })

    it('supports direct IPv4 hostnames without wildcard subdomain syntax', () => {
      const patterns = buildUrlPatterns(['127.0.0.1:8000', '192.168.1.10'])
      expect(patterns).toEqual(['*://127.0.0.1/*', '*://192.168.1.10/*'])
    })

    it('deduplicates domains and drops invalid entries', () => {
      const patterns = buildUrlPatterns(['18comic.vip', '18comic.vip', '', '   '])
      expect(patterns).toEqual(['*://*.18comic.vip/*'])
    })
  })
})

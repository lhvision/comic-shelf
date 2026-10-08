import { describe, it, expect } from 'vite-plus/test'
import {
  isSafeUrl,
  resolveComicInfo,
  buildUrlPatterns,
  detectComicFromTab,
} from '../../extension/service-worker.js'
import {
  sanitizeDomain,
  isValidDomain,
  BUILTIN_PROVIDERS,
  DEFAULT_DOMAINS,
} from '../../extension/constants.js'

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

  describe('extension constants & domain tools', () => {
    it('provides valid BUILTIN_PROVIDERS with expected domains and badges', () => {
      expect(BUILTIN_PROVIDERS.length).toBe(3)
      const jm = BUILTIN_PROVIDERS.find(
        (p: { source: string; badge: string; domains: string[] }) => p.source === 'jm',
      )
      expect(jm?.badge).toBe('JM')
      expect(jm?.domains).toContain('18comic.vip')
      expect(DEFAULT_DOMAINS.length).toBe(20)
    })

    it('sanitizes messy domain inputs correctly', () => {
      expect(sanitizeDomain('https://comic18j-mirror.xyz/album/123')).toBe('comic18j-mirror.xyz')
      expect(sanitizeDomain('  http://PICACOMIC.COM:443/  ')).toBe('picacomic.com')
      expect(sanitizeDomain('*.copymanga.tv')).toBe('copymanga.tv')
      expect(sanitizeDomain('')).toBe('')
    })

    it('validates domain strings accurately', () => {
      expect(isValidDomain('comic18j-mirror.xyz')).toBe(true)
      expect(isValidDomain('192.168.1.100')).toBe(true)
      expect(isValidDomain('localhost')).toBe(true)
      expect(isValidDomain('invalid..domain')).toBe(false)
      expect(isValidDomain('not a domain')).toBe(false)
      expect(isValidDomain('')).toBe(false)
    })
  })

  describe('context-aware icon click & site navigation', () => {
    describe('detectComicFromTab', () => {
      it('detects comic info on an active tab with a valid comic URL', async () => {
        const tab = { id: 1, url: 'https://18comic.vip/album/123456' }
        const res = await detectComicFromTab(tab)
        expect(res?.comic).toEqual({
          source: 'jm',
          id: '123456',
          name: '禁漫天堂',
        })
      })

      it('returns null when tab URL is not a comic page', async () => {
        const tab = { id: 2, url: 'https://google.com/search' }
        const res = await detectComicFromTab(tab)
        expect(res).toBeNull()
      })

      it('detects comic info from pendingUrl when tab is still navigating', async () => {
        const tab = { id: 10, pendingUrl: 'https://copymanga.tv/comic/dandadan' }
        const res = await detectComicFromTab(tab)
        expect(res?.comic).toEqual({
          source: 'copymanga',
          id: 'dandadan',
          name: '拷贝漫画',
        })
      })

      it('detects comic info with hash-based single page app routing', async () => {
        const tab = { id: 11, url: 'https://mirror.org/#/comic/chainsaw-man' }
        const res = await detectComicFromTab(tab)
        expect(res?.comic).toEqual({
          source: 'copymanga',
          id: 'chainsaw-man',
          name: '拷贝漫画',
        })
      })

      it('returns null when tab or url is invalid', async () => {
        expect(await detectComicFromTab(null)).toBeNull()
        expect(await detectComicFromTab({ id: 3, url: 'javascript:alert(1)' })).toBeNull()
      })
    })
  })
})

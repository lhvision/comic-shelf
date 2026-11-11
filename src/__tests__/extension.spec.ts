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
  createEmptyCustomDomainsMap,
  guessProviderFromDomain,
  findDomainOwner,
  migrateCustomDomains,
  matchDomainToProvider,
  getAllConfiguredDomains,
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

    it('supports direct IPv4 hostnames and localhost without wildcard subdomain syntax', () => {
      const patterns = buildUrlPatterns(['127.0.0.1:8000', '192.168.1.10', 'localhost'])
      expect(patterns).toEqual(['*://127.0.0.1/*', '*://192.168.1.10/*', '*://localhost/*'])
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
      expect(DEFAULT_DOMAINS.length).toBe(11)
    })

    it('sanitizes messy domain inputs correctly (including query strings and hash anchors)', () => {
      expect(sanitizeDomain('https://comic18j-mirror.xyz/album/123')).toBe('comic18j-mirror.xyz')
      expect(sanitizeDomain('  http://MANHUAPICA.COM:443/  ')).toBe('manhuapica.com')
      expect(sanitizeDomain('*.mangacopy.com')).toBe('mangacopy.com')
      expect(sanitizeDomain('comic18.vip?source=share&utm=test')).toBe('comic18.vip')
      expect(sanitizeDomain('manhuapica.com#heading-1')).toBe('manhuapica.com')
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

  describe('provider-bound custom domains & global uniqueness', () => {
    it('creates an empty custom domains dictionary for all builtin providers', () => {
      const empty = createEmptyCustomDomainsMap()
      expect(empty).toEqual({
        jm: [],
        picacg: [],
        copymanga: [],
      })
    })

    it('guesses provider heuristically from domain features', () => {
      expect(guessProviderFromDomain('comic18j-mirror.xyz')).toBe('jm')
      expect(guessProviderFromDomain('jmcomic-zzz.org')).toBe('jm')
      expect(guessProviderFromDomain('https://manhuapica.com/comic/123')).toBe('picacg')
      expect(guessProviderFromDomain('mangacopy.tv')).toBe('copymanga')
      expect(guessProviderFromDomain('copy4000.net')).toBe('copymanga')
      expect(guessProviderFromDomain('unknown-site.org')).toBeNull()
    })

    it('enforces global uniqueness and correctly finds domain owners', () => {
      const customMap = {
        jm: ['custom-jm.org'],
        picacg: ['custom-pica.com'],
        copymanga: ['custom-copy.tv'],
      }

      // 1. 系统内置域名 (精确匹配)
      const builtinOwner = findDomainOwner('18comic.vip', customMap)
      expect(builtinOwner).toEqual({
        source: 'jm',
        name: '禁漫天堂',
        badge: 'JM',
        isBuiltin: true,
        conflictType: 'exact',
        conflictDomain: '18comic.vip',
      })

      // 2. 自定义域名 (精确匹配)
      const customOwner = findDomainOwner('custom-copy.tv', customMap)
      expect(customOwner).toEqual({
        source: 'copymanga',
        name: '拷贝漫画',
        badge: '拷贝',
        isBuiltin: false,
        conflictType: 'exact',
        conflictDomain: 'custom-copy.tv',
      })

      // 3. 子域名重叠冲突拦截
      const subOwner = findDomainOwner('sub.18comic.vip', customMap)
      expect(subOwner).toEqual({
        source: 'jm',
        name: '禁漫天堂',
        badge: 'JM',
        isBuiltin: true,
        conflictType: 'subdomain',
        conflictDomain: '18comic.vip',
      })

      // 4. 父域名重叠冲突拦截
      const parentOwner = findDomainOwner('custom-jm.org', {
        ...customMap,
        jm: ['sub.custom-jm.org'],
      })
      expect(parentOwner?.conflictType).toBe('parent')

      // 5. 未被占用的全新域名
      expect(findDomainOwner('brand-new-domain.com', customMap)).toBeNull()
    })

    it('migrates legacy flat domain array to provider map without duplicates', () => {
      const legacy = [
        '18comic.vip', // 与系统内置重复，应被过滤
        'comic18j-mirror.xyz', // 归入 jm
        'pica-share.net', // 归入 picacg
        'copymanga-mirror.org', // 归入 copymanga
        'general-mirror.com', // 启发式无法确定时保守归入 jm
        'comic18j-mirror.xyz', // 重复项，应去重
      ]

      const migrated = migrateCustomDomains(legacy)
      expect(migrated.jm).toContain('comic18j-mirror.xyz')
      expect(migrated.jm).toContain('general-mirror.com')
      expect(migrated.jm).not.toContain('18comic.vip')
      expect(migrated.picacg).toEqual(['pica-share.net'])
      expect(migrated.copymanga).toEqual(['copymanga-mirror.org'])
      expect(migrated.jm?.filter((d) => d === 'comic18j-mirror.xyz').length).toBe(1)
    })

    it('matches domain and subdomains to the exact owning provider', () => {
      const customMap = {
        jm: ['custom-jm.org'],
        picacg: ['custom-pica.com'],
        copymanga: ['custom-copy.tv'],
      }

      const matchBuiltin = matchDomainToProvider('sub.18comic.vip', customMap)
      expect(matchBuiltin?.source).toBe('jm')

      const matchCustom = matchDomainToProvider('reader.custom-copy.tv', customMap)
      expect(matchCustom?.source).toBe('copymanga')

      const matchNone = matchDomainToProvider('example.com', customMap)
      expect(matchNone).toBeNull()
    })

    it('retrieves all configured domains deduplicated', () => {
      const customMap = {
        jm: ['custom-jm.org', '18comic.vip'], // 包含一个与内置重复的
        picacg: ['custom-pica.com'],
        copymanga: [],
      }

      const all = getAllConfiguredDomains(customMap)
      expect(all).toContain('18comic.vip')
      expect(all).toContain('custom-jm.org')
      expect(all).toContain('custom-pica.com')
      // 确认无重复项
      expect(new Set(all).size).toBe(all.length)
    })
  })

  describe('source-hint locked resolution in resolveComicInfo', () => {
    it('resolves CopyManga even when slug is a 24-char hex string when sourceHint is copymanga', () => {
      // 拷贝漫画的 slug 碰巧是 24 位十六进制，在未指定 sourceHint 时易被误认为哔咔
      const hexSlugUrl = 'https://custom-copy.tv/comic/5ebe89bf89196b0559e21bf4'

      const defaultResolution = resolveComicInfo(hexSlugUrl)
      expect(defaultResolution?.source).toBe('picacg')

      // 在绑定 copymanga 图源上下文后，严格解析为 copymanga，杜绝跨源误判
      const lockedResolution = resolveComicInfo(hexSlugUrl, 'copymanga')
      expect(lockedResolution).toEqual({
        source: 'copymanga',
        id: '5ebe89bf89196b0559e21bf4',
        name: '拷贝漫画',
      })
    })

    it('rejects invalid path for the locked provider without cross-source fallback', () => {
      const copyUrl = 'https://custom-jm.org/comic/chainsaw-man'
      // 即使路径符合拷贝漫画，如果当前锁定为 jm 图源，绝不返回拷贝结果
      const res = resolveComicInfo(copyUrl, 'jm')
      expect(res).toBeNull()
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

      it('supports subdomains of supported providers', async () => {
        const tab = { id: 1, url: 'https://m.18comic.vip/album/123456' }
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

      it('rejects Paper Room self-origin URLs to prevent misidentifying own route as CopyManga', async () => {
        const tab = { id: 3, url: 'http://localhost:8000/comic/jm/123456' }
        const res = await detectComicFromTab(tab, { serverUrl: 'http://localhost:8000' })
        expect(res).toBeNull()
      })

      it('rejects unrelated sites with /comic/ or /album/ in path/hash', async () => {
        const tabGithub = { id: 4, url: 'https://github.com/comic/some-repo' }
        expect(await detectComicFromTab(tabGithub)).toBeNull()

        const tabMusic = { id: 5, url: 'https://music.163.com/#/album/12345' }
        expect(await detectComicFromTab(tabMusic)).toBeNull()
      })

      it('detects comic info from pendingUrl when tab is still navigating', async () => {
        const tab = { id: 10, pendingUrl: 'https://mangacopy.com/comic/dandadan' }
        const res = await detectComicFromTab(tab)
        expect(res?.comic).toEqual({
          source: 'copymanga',
          id: 'dandadan',
          name: '拷贝漫画',
        })
      })

      it('detects comic info with hash-based single page app routing on allowed custom domains', async () => {
        const tab = { id: 11, url: 'https://mirror.org/#/comic/chainsaw-man' }
        const res = await detectComicFromTab(tab, {
          customDomains: { copymanga: ['mirror.org'] },
        })
        expect(res?.comic).toEqual({
          source: 'copymanga',
          id: 'chainsaw-man',
          name: '拷贝漫画',
        })
      })

      it('accurately resolves comic source based on domain binding without heuristic confusion', async () => {
        const customDomains = {
          jm: ['jm-custom.org'],
          picacg: [],
          copymanga: ['copy-custom.tv'],
        }

        // On CopyManga custom domain with hex slug: should resolve as CopyManga
        const tabCopy = {
          id: 12,
          url: 'https://copy-custom.tv/comic/5ebe89bf89196b0559e21bf4',
        }
        const resCopy = await detectComicFromTab(tabCopy, { customDomains })
        expect(resCopy?.comic).toEqual({
          source: 'copymanga',
          id: '5ebe89bf89196b0559e21bf4',
          name: '拷贝漫画',
        })

        // On JM custom domain: should resolve as JM
        const tabJm = {
          id: 13,
          url: 'https://jm-custom.org/album/998877',
        }
        const resJm = await detectComicFromTab(tabJm, { customDomains })
        expect(resJm?.comic).toEqual({
          source: 'jm',
          id: '998877',
          name: '禁漫天堂',
        })
      })

      it('returns null when tab or url is invalid', async () => {
        expect(await detectComicFromTab(null)).toBeNull()
        expect(await detectComicFromTab({ id: 3, url: 'javascript:alert(1)' })).toBeNull()
      })
    })
  })
})

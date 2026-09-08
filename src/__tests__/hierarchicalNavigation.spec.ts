import { describe, expect, it, vi, beforeEach, afterEach } from 'vite-plus/test'
import type { Router } from 'vue-router'
import {
  isChildRoute,
  isParentAlbumRoute,
  isSafeUpstreamRoute,
  navigateUpFromChapter,
  switchChapter,
  navigateUpFromDetail,
  navigateUpFromCreate,
} from '@/composables/useHierarchicalNavigation'

describe('useHierarchicalNavigation & Downward Navigation Guard', () => {
  let mockBack: ReturnType<typeof vi.fn<() => void>>
  let mockReplace: ReturnType<typeof vi.fn<(to: unknown) => Promise<unknown>>>
  let mockPush: ReturnType<typeof vi.fn<(to: unknown) => Promise<unknown>>>
  let mockRouter: Router

  beforeEach(() => {
    mockBack = vi.fn<() => void>()
    mockReplace = vi.fn<(to: unknown) => Promise<unknown>>()
    mockPush = vi.fn<(to: unknown) => Promise<unknown>>()
    mockRouter = {
      back: mockBack,
      replace: mockReplace,
      push: mockPush,
    } as unknown as Router

    // 默认清空 history.state
    window.history.replaceState(null, '', window.location.href)
  })

  afterEach(() => {
    window.history.replaceState(null, '', window.location.href)
  })

  describe('isChildRoute predicate', () => {
    const parent = '/comic/jm/123'

    it('identifies chapter subroutes as child routes', () => {
      expect(isChildRoute(parent, '/comic/jm/123/chapter/ch1')).toBe(true)
      expect(isChildRoute(parent, '/comic/jm/123/chapter/ch-test-99')).toBe(true)
    })

    it('identifies reader subroutes as child routes', () => {
      expect(isChildRoute(parent, '/comic/jm/123/read/1')).toBe(true)
      expect(isChildRoute(parent, '/comic/jm/123/read/15?chapter=ch1')).toBe(true)
    })

    it('handles trailing slash on parent path', () => {
      expect(isChildRoute('/comic/jm/123/', '/comic/jm/123/chapter/ch1')).toBe(true)
    })

    it('returns false for the exact parent path itself', () => {
      expect(isChildRoute(parent, '/comic/jm/123')).toBe(false)
    })

    it('returns false for upper-level or sibling routes', () => {
      expect(isChildRoute(parent, '/')).toBe(false)
      expect(isChildRoute(parent, '/?source=jm')).toBe(false)
      expect(isChildRoute(parent, '/discovery')).toBe(false)
      expect(isChildRoute(parent, '/comic/jm/123456')).toBe(false)
      expect(isChildRoute(parent, '/comic/picacg/123/chapter/1')).toBe(false)
    })

    it('returns false on empty or falsy arguments', () => {
      expect(isChildRoute('', '/comic/jm/123')).toBe(false)
      expect(isChildRoute(parent, '')).toBe(false)
    })
  })

  describe('isParentAlbumRoute predicate', () => {
    const albumPath = '/comic/jm/123'

    it('returns true for exact album route', () => {
      expect(isParentAlbumRoute(albumPath, '/comic/jm/123')).toBe(true)
    })

    it('returns true for album route with query parameters or hash', () => {
      expect(isParentAlbumRoute(albumPath, '/comic/jm/123?tab=chapters')).toBe(true)
      expect(isParentAlbumRoute(albumPath, '/comic/jm/123#top')).toBe(true)
    })

    it('returns false for child routes or other routes', () => {
      expect(isParentAlbumRoute(albumPath, '/comic/jm/123/chapter/ch1')).toBe(false)
      expect(isParentAlbumRoute(albumPath, '/')).toBe(false)
      expect(isParentAlbumRoute(albumPath, '/discovery')).toBe(false)
      expect(isParentAlbumRoute(albumPath, undefined)).toBe(false)
      expect(isParentAlbumRoute(albumPath, null)).toBe(false)
    })
  })

  describe('navigateUpFromChapter', () => {
    it('pops history with router.back() when history.state.back points to the parent album', () => {
      window.history.replaceState({ back: '/comic/jm/518074' }, '', window.location.href)

      navigateUpFromChapter(mockRouter, 'jm', '518074')

      expect(mockBack).toHaveBeenCalledTimes(1)
      expect(mockReplace).not.toHaveBeenCalled()
    })

    it('falls back to router.replace with the album path when history.state.back is missing (cold start)', () => {
      window.history.replaceState(null, '', window.location.href)

      navigateUpFromChapter(mockRouter, 'jm', '518074')

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith('/comic/jm/518074')
    })

    it('falls back to router.replace when history.state.back points to an unrelated page', () => {
      window.history.replaceState({ back: '/discovery' }, '', window.location.href)

      navigateUpFromChapter(mockRouter, 'jm', '518074')

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith('/comic/jm/518074')
    })
  })

  describe('switchChapter', () => {
    it('uses router.replace to switch chapters within the same viewport model', () => {
      switchChapter(mockRouter, 'jm', '518074', 'ch-2')

      expect(mockReplace).toHaveBeenCalledWith('/comic/jm/518074/chapter/ch-2')
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('encodes chapter IDs with special characters', () => {
      switchChapter(mockRouter, 'jm', '518074', 'ch 2/extra')

      expect(mockReplace).toHaveBeenCalledWith('/comic/jm/518074/chapter/ch%202%2Fextra')
    })
  })

  describe('navigateUpFromDetail (Downward Navigation Guard)', () => {
    it('allows router.back() when back points to library root', () => {
      window.history.replaceState({ back: '/' }, '', window.location.href)

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      expect(mockBack).toHaveBeenCalledTimes(1)
      expect(mockReplace).not.toHaveBeenCalled()
    })

    it('allows router.back() when back points to library with search/filter query', () => {
      window.history.replaceState({ back: '/?source=jm&tag=cat' }, '', window.location.href)

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      expect(mockBack).toHaveBeenCalledTimes(1)
      expect(mockReplace).not.toHaveBeenCalled()
    })

    it('allows router.back() when back points to discovery', () => {
      window.history.replaceState({ back: '/discovery' }, '', window.location.href)

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      expect(mockBack).toHaveBeenCalledTimes(1)
      expect(mockReplace).not.toHaveBeenCalled()
    })

    it('blocks router.back() and replaces with library when back is a chapter subroute of this comic', () => {
      window.history.replaceState(
        { back: '/comic/jm/518074/chapter/ch-1' },
        '',
        window.location.href,
      )

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      // 绝不后退进入子章节，触发纵深防御回退至书架
      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('blocks router.back() and replaces with library when back is a reader subroute of this comic', () => {
      window.history.replaceState(
        { back: '/comic/jm/518074/read/12?chapter=ch-1' },
        '',
        window.location.href,
      )

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('blocks router.back() and replaces with library when back is a reader of another comic (e.g. from end recommendation)', () => {
      window.history.replaceState({ back: '/comic/jm/12345/read/50' }, '', window.location.href)

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('blocks router.back() and replaces with library when back is the creation workshop (/create)', () => {
      window.history.replaceState({ back: '/create' }, '', window.location.href)

      navigateUpFromDetail(mockRouter, 'local', 'my-comic')

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('blocks router.back() and replaces with library when back points to the same album (e.g. replaced from reader)', () => {
      window.history.replaceState({ back: '/comic/jm/518074' }, '', window.location.href)

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('falls back to router.replace with library when history.state.back is missing', () => {
      window.history.replaceState(null, '', window.location.href)

      navigateUpFromDetail(mockRouter, 'jm', '518074')

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })
  })

  describe('isSafeUpstreamRoute predicate', () => {
    const detail = '/comic/jm/518074'

    it('returns true for library and discovery routes', () => {
      expect(isSafeUpstreamRoute(detail, '/')).toBe(true)
      expect(isSafeUpstreamRoute(detail, '/?source=jm&tag=cat')).toBe(true)
      expect(isSafeUpstreamRoute(detail, '/discovery')).toBe(true)
      expect(isSafeUpstreamRoute(detail, '/discovery?tab=ranking')).toBe(true)
    })

    it('returns true for peer album detail routes (e.g. recommendation navigation)', () => {
      expect(isSafeUpstreamRoute(detail, '/comic/jm/999999')).toBe(true)
    })

    it('returns false for the same album detail route (prevents double-back bounce)', () => {
      expect(isSafeUpstreamRoute(detail, '/comic/jm/518074')).toBe(false)
      expect(isSafeUpstreamRoute(detail, '/comic/jm/518074/')).toBe(false)
      expect(isSafeUpstreamRoute(detail, '/comic/jm/518074?tab=chapters')).toBe(false)
      expect(isSafeUpstreamRoute(detail, '/comic/jm/518074#c1')).toBe(false)
    })

    it('returns false for child chapter and reader routes of this comic', () => {
      expect(isSafeUpstreamRoute(detail, '/comic/jm/518074/chapter/1')).toBe(false)
      expect(isSafeUpstreamRoute(detail, '/comic/jm/518074/read/10')).toBe(false)
    })

    it('returns false for any reader route regardless of comic', () => {
      expect(isSafeUpstreamRoute(detail, '/comic/other/123/read/1')).toBe(false)
    })

    it('returns false for any chapter route regardless of comic', () => {
      expect(isSafeUpstreamRoute(detail, '/comic/other/123/chapter/1')).toBe(false)
    })

    it('returns false for /create form routes', () => {
      expect(isSafeUpstreamRoute(detail, '/create')).toBe(false)
      expect(isSafeUpstreamRoute(detail, '/create?mode=upload')).toBe(false)
      expect(isSafeUpstreamRoute(detail, '/create#options')).toBe(false)
    })

    it('returns false for null, undefined, or empty back state', () => {
      expect(isSafeUpstreamRoute(detail, null)).toBe(false)
      expect(isSafeUpstreamRoute(detail, undefined)).toBe(false)
      expect(isSafeUpstreamRoute(detail, '')).toBe(false)
    })

    it('returns false for external, protocol-relative, or non-pathname strings (open-redirect defense)', () => {
      expect(isSafeUpstreamRoute(detail, '//evil.com')).toBe(false)
      expect(isSafeUpstreamRoute(detail, 'https://evil.com')).toBe(false)
      expect(isSafeUpstreamRoute(detail, 'javascript:alert(1)')).toBe(false)
      expect(isSafeUpstreamRoute(detail, 'data:text/html,test')).toBe(false)
    })

    it('evaluates meta.rank via router.resolve when router is provided', () => {
      const mockResolveRouter = {
        resolve: vi.fn<(path: string) => { name?: string; meta?: { rank?: number } }>(
          (path: string) => {
            if (path.startsWith('/custom/deep-reader')) {
              return { meta: { rank: 4 } }
            }
            if (path.startsWith('/custom/deep-chapter')) {
              return { meta: { rank: 3 } }
            }
            if (path === '/custom-workshop') {
              return { name: 'create-comic', meta: { rank: 2 } }
            }
            if (path === '/discovery') {
              return { meta: { rank: 1 } }
            }
            return { meta: { rank: 2 } }
          },
        ),
      } as unknown as Router

      // Rank 4 & Rank 3 are blocked via metadata
      expect(isSafeUpstreamRoute(detail, '/custom/deep-reader/1', mockResolveRouter)).toBe(false)
      expect(isSafeUpstreamRoute(detail, '/custom/deep-chapter/1', mockResolveRouter)).toBe(false)
      // Form name 'create-comic' is blocked via metadata
      expect(isSafeUpstreamRoute(detail, '/custom-workshop', mockResolveRouter)).toBe(false)
      // Rank 1 is allowed
      expect(isSafeUpstreamRoute(detail, '/discovery', mockResolveRouter)).toBe(true)
    })
  })

  describe('navigateUpFromCreate', () => {
    it('calls router.back() when history.state.back is library or discovery', () => {
      window.history.replaceState({ back: '/' }, '', window.location.href)

      navigateUpFromCreate(mockRouter)

      expect(mockBack).toHaveBeenCalledTimes(1)
      expect(mockReplace).not.toHaveBeenCalled()
    })

    it('blocks router.back() and replaces with library when back points to a reader', () => {
      window.history.replaceState({ back: '/comic/jm/123/read/1' }, '', window.location.href)

      navigateUpFromCreate(mockRouter)

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('blocks router.back() and replaces with library when back points to /create itself', () => {
      window.history.replaceState({ back: '/create' }, '', window.location.href)

      navigateUpFromCreate(mockRouter)

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('blocks router.back() and replaces with library when back points to /create with query', () => {
      window.history.replaceState({ back: '/create?step=2' }, '', window.location.href)

      navigateUpFromCreate(mockRouter)

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })

    it('falls back to router.replace with library when history.state.back is missing', () => {
      window.history.replaceState(null, '', window.location.href)

      navigateUpFromCreate(mockRouter)

      expect(mockBack).not.toHaveBeenCalled()
      expect(mockReplace).toHaveBeenCalledWith({ name: 'library' })
    })
  })
})

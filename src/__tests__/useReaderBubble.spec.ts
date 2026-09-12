import { describe, it, expect } from 'vite-plus/test'
import { parseBubbleBox, useReaderBubble, DEFAULT_BUBBLE_BOX } from '@/composables/useReaderBubble'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

function createMockRoute(
  query: Record<string, string | string[] | undefined> = {},
  params: Record<string, string | string[] | undefined> = {},
): RouteLocationNormalizedLoaded {
  return {
    query,
    params,
    fullPath: '',
    hash: '',
    matched: [],
    meta: {},
    name: 'reader',
    path: '/comic/jm/123/read',
    redirectedFrom: undefined,
  } as unknown as RouteLocationNormalizedLoaded
}

describe('useReaderBubble', () => {
  describe('parseBubbleBox', () => {
    it('parses comma-separated strings', () => {
      const box = parseBubbleBox('0.1,0.2,0.3,0.4')
      expect(box).toEqual([0.1, 0.2, 0.3, 0.4])
    })

    it('parses bracket-enclosed strings and spaces', () => {
      const box = parseBubbleBox('[0.12, 0.45, 0.28, 0.68]')
      expect(box).toEqual([0.12, 0.45, 0.28, 0.68])
    })

    it('clamps values between 0 and 1', () => {
      const box = parseBubbleBox('-0.2, -0.1, 1.5, 1.2')
      expect(box).toEqual([0, 0, 1, 1])
    })

    it('adaptively normalizes 0..1000 integer coordinates', () => {
      const box = parseBubbleBox('[182, 128, 318, 382]')
      expect(box).toEqual([0.182, 0.128, 0.318, 0.382])
    })

    it('adaptively normalizes 0..100 percentage coordinates', () => {
      const box = parseBubbleBox('12, 45, 28, 68')
      expect(box).toEqual([0.12, 0.45, 0.28, 0.68])
    })

    it('returns null for malformed or insufficient coordinates', () => {
      expect(parseBubbleBox('0.1,0.2,abc,0.4')).toBeNull()
      expect(parseBubbleBox('0.1,0.2,0.3')).toBeNull()
      expect(parseBubbleBox('')).toBeNull()
      expect(parseBubbleBox(null)).toBeNull()
    })
  })

  describe('useReaderBubble composable', () => {
    it('returns null targetBubble when no query params are present', () => {
      const route = createMockRoute({}, { page: '1' })
      const { targetBubble, targetPage } = useReaderBubble(route)

      expect(targetPage.value).toBe(1)
      expect(targetBubble.value).toBeNull()
    })

    it('parses query page and bubble_box correctly', () => {
      const route = createMockRoute({
        page: '42',
        bubble_box: '0.1,0.2,0.3,0.4',
        text: '这就是最后的波纹吗……',
      })
      const { targetBubble, targetPage } = useReaderBubble(route)

      expect(targetPage.value).toBe(42)
      expect(targetBubble.value).toEqual({
        page: 42,
        box: [0.1, 0.2, 0.3, 0.4],
        text: '这就是最后的波纹吗……',
      })
    })

    it('supports highlight_bubble=1 with default box fallback', () => {
      const route = createMockRoute({
        page: '15',
        highlight_bubble: '1',
      })
      const { targetBubble, targetPage } = useReaderBubble(route)

      expect(targetPage.value).toBe(15)
      expect(targetBubble.value).toEqual({
        page: 15,
        box: DEFAULT_BUBBLE_BOX,
      })
    })

    it('extracts page from route params if query page is omitted', () => {
      const route = createMockRoute(
        {
          bubble_box: '0.2,0.3,0.5,0.7',
        },
        { page: '8' },
      )
      const { targetBubble, targetPage } = useReaderBubble(route)

      expect(targetPage.value).toBe(8)
      expect(targetBubble.value?.page).toBe(8)
      expect(targetBubble.value?.box).toEqual([0.2, 0.3, 0.5, 0.7])
    })

    it('dismisses bubble and silently erases query params via router.replace', () => {
      const route = createMockRoute({
        page: '12',
        bubble_box: '0.1,0.2,0.3,0.4',
        bubble_text: '荒木庄',
        highlight_bubble: '1',
      })
      let replacedQuery: Record<string, unknown> | null = null
      const mockRouter = {
        replace: (loc: { query: Record<string, unknown> }) => {
          replacedQuery = loc.query
          return Promise.resolve()
        },
      } as unknown as import('vue-router').Router

      const { targetBubble, dismissBubble } = useReaderBubble(route, mockRouter)
      expect(targetBubble.value).not.toBeNull()

      dismissBubble()
      expect(targetBubble.value).toBeNull()
      expect(replacedQuery).toEqual({ page: '12' })
    })
  })
})

import { describe, it, expect, vi } from 'vite-plus/test'
import {
  parseBubbleBox,
  parseBubbleBoxes,
  serializeBubbleBox,
  serializeBubbleBoxes,
  useReaderBubble,
  DEFAULT_BUBBLE_BOX,
  MAX_HIGHLIGHT_BOXES,
} from '@/composables/useReaderBubble'
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

  describe('parseBubbleBoxes / serializeBubbleBoxes', () => {
    it('parses semicolon-joined sibling boxes and drops only the malformed segment', () => {
      expect(parseBubbleBoxes('0.1,0.2,0.3,0.4;junk;0.5,0.6,0.7,0.8')).toEqual([
        [0.1, 0.2, 0.3, 0.4],
        [0.5, 0.6, 0.7, 0.8],
      ])
    })

    it('returns an empty list for missing or blank params', () => {
      expect(parseBubbleBoxes(undefined)).toEqual([])
      expect(parseBubbleBoxes('')).toEqual([])
      expect(parseBubbleBoxes(42)).toEqual([])
    })

    it('round-trips through the serializer used when navigating from search', () => {
      const boxes = [
        [0.4288, 0.1573, 0.5077, 0.2156],
        [0.6066, 0.2615, 0.7077, 0.2927],
      ]
      expect(parseBubbleBoxes(serializeBubbleBoxes(boxes))).toEqual(boxes)
      expect(serializeBubbleBoxes(undefined)).toBe('')
      expect(
        serializeBubbleBoxes([
          [0.1, 0.2],
          [0.1, 0.2, 0.3, 0.4],
        ]),
      ).toBe('0.1000,0.2000,0.3000,0.4000')
    })

    it('refuses to encode non-finite coordinates into the URL', () => {
      // MCP 传入的坐标可能缺元素，Number(undefined) 是 NaN，直接 toFixed 会拼出
      // bubble_box=NaN,NaN,NaN,NaN —— 阅读器解析得到 null，高亮静默消失
      expect(serializeBubbleBox([Number.NaN, 0.2, 0.3, 0.4])).toBeNull()
      expect(serializeBubbleBox([undefined as unknown as number, 0.2, 0.3, 0.4])).toBeNull()
      expect(serializeBubbleBox([])).toBeNull()
      expect(
        serializeBubbleBoxes([
          [Number.NaN, 0.1, 0.2, 0.3],
          [0.1, 0.2, 0.3, 0.4],
        ]),
      ).toBe('0.1000,0.2000,0.3000,0.4000')
    })

    it('caps sibling frames at MAX_HIGHLIGHT_BOXES - 1 against a hand-edited URL', () => {
      const flooded = Array.from({ length: 20 }, (_, i) => `0.1,0.2,0.3,0.4${i % 10}`).join(';')
      expect(parseBubbleBoxes(flooded)).toHaveLength(MAX_HIGHLIGHT_BOXES - 1)
    })

    it('caps the serialized side too, so maxItems is not the only guard', () => {
      const many = Array.from({ length: 20 }, (_, i) => [0.1, 0.2, 0.3, 0.401 + i / 1000])
      expect(serializeBubbleBoxes(many).split(';')).toHaveLength(MAX_HIGHLIGHT_BOXES - 1)
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

    it('carries same-page sibling boxes on targetBubble.others', () => {
      const route = createMockRoute({
        page: '16',
        bubble_box: '0.4288,0.1573,0.5077,0.2156',
        bubble_boxes: '0.6066,0.2615,0.7077,0.2927;0.03,0.1,0.2,0.3',
      })
      const { targetBubble } = useReaderBubble(route)

      // 代表格语义不变：仍是定位与 callout 的那一格，siblings 只是叠加
      expect(targetBubble.value?.box).toEqual([0.4288, 0.1573, 0.5077, 0.2156])
      expect(targetBubble.value?.others).toEqual([
        [0.6066, 0.2615, 0.7077, 0.2927],
        [0.03, 0.1, 0.2, 0.3],
      ])
    })

    it('auto-dismisses a highlight_bubble-only URL that carries no bubble_box', () => {
      // 回归：watch 源数组曾按位置解构，插入 bubble_boxes 后把 highlight_bubble 挤出
      // 触发条件，这条无 box 的遥控 URL 会渲染出基准框却永不自愈、参数永不擦除
      const route = createMockRoute({ page: '42', highlight_bubble: '1' })
      let replacedQuery: Record<string, unknown> | null = null
      const mockRouter = {
        replace: (loc: { query: Record<string, unknown> }) => {
          replacedQuery = loc.query
          return Promise.resolve()
        },
      } as unknown as import('vue-router').Router

      // 自动熄灭定时器在 composable 创建时就排下，fake timers 必须包住创建
      vi.useFakeTimers()
      try {
        const { targetBubble } = useReaderBubble(route, mockRouter)
        expect(targetBubble.value?.box).toEqual(DEFAULT_BUBBLE_BOX)

        vi.advanceTimersByTime(2900)

        expect(targetBubble.value).toBeNull()
        expect(replacedQuery).toEqual({ page: '42' })
      } finally {
        vi.useRealTimers()
      }
    })

    it('promotes the first valid sibling when the representative is missing or malformed', () => {
      // 弹层承诺了「这一页命中 N 处」，代表格缺失/畸形都不能让同页其余格跟着消失
      const noRep = createMockRoute({
        page: '3',
        bubble_boxes: '0.1,0.2,0.3,0.4;0.5,0.6,0.7,0.8',
      })
      const promoted = useReaderBubble(noRep).targetBubble.value
      expect(promoted?.box).toEqual([0.1, 0.2, 0.3, 0.4])
      // 被提升的那一格不能再重复描一遍静态边
      expect(promoted?.others).toEqual([[0.5, 0.6, 0.7, 0.8]])

      const badRep = createMockRoute({
        page: '3',
        highlight_bubble: '1',
        bubble_box: '0.1,0.2',
        bubble_boxes: '0.5,0.6,0.7,0.8',
      })
      expect(useReaderBubble(badRep).targetBubble.value?.box).toEqual([0.5, 0.6, 0.7, 0.8])
    })

    it('falls back to the placeholder box only when no valid coordinate exists at all', () => {
      const route = createMockRoute({ page: '3', highlight_bubble: '1', bubble_box: 'garbage' })
      const { targetBubble } = useReaderBubble(route)

      expect(targetBubble.value?.box).toEqual(DEFAULT_BUBBLE_BOX)
      expect(targetBubble.value?.others).toBeUndefined()
    })

    it('leaves others unset when every sibling segment is malformed', () => {
      const route = createMockRoute({
        page: '3',
        bubble_box: '0.1,0.2,0.3,0.4',
        bubble_boxes: 'garbage;0.5,0.6',
      })
      const { targetBubble } = useReaderBubble(route)

      expect(targetBubble.value?.box).toEqual([0.1, 0.2, 0.3, 0.4])
      expect(targetBubble.value?.others).toBeUndefined()
    })

    it('erases bubble_boxes from the URL together with the highlight params', () => {
      const route = createMockRoute({
        page: '16',
        bubble_box: '0.1,0.2,0.3,0.4',
        bubble_boxes: '0.5,0.6,0.7,0.8',
      })
      let replacedQuery: Record<string, unknown> | null = null
      const mockRouter = {
        replace: (loc: { query: Record<string, unknown> }) => {
          replacedQuery = loc.query
          return Promise.resolve()
        },
      } as unknown as import('vue-router').Router

      const { dismissBubble } = useReaderBubble(route, mockRouter)
      dismissBubble()

      // 残留会让刷新后出现没有主体的空描边框
      expect(replacedQuery).toEqual({ page: '16' })
    })
  })
})

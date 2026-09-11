import { describe, it, expect, vi, afterEach } from 'vite-plus/test'
import { isDrawElementSupported, isLayoutSubtreeSupported } from '@/utils/canvasProbe'

describe('canvasProbe', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('detects drawElementImage capability correctly', () => {
    // In JSDOM / standard Vitest, drawElementImage is not implemented by default
    expect(isDrawElementSupported()).toBe(false)

    // Mock presence
    const origCtx = (window as unknown as { CanvasRenderingContext2D?: unknown })
      .CanvasRenderingContext2D
    const mockCtxClass = class {} as unknown as { prototype: { drawElementImage?: () => void } }
    mockCtxClass.prototype.drawElementImage = () => {}
    ;(window as unknown as { CanvasRenderingContext2D?: unknown }).CanvasRenderingContext2D =
      mockCtxClass

    expect(isDrawElementSupported()).toBe(true)

    ;(window as unknown as { CanvasRenderingContext2D?: unknown }).CanvasRenderingContext2D =
      origCtx
  })

  it('detects layoutsubtree property correctly', () => {
    // Standard JSDOM does not have layoutSubtree
    expect(isLayoutSubtreeSupported()).toBe(false)

    const origCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      const el = origCreateElement(tagName)
      if (tagName === 'canvas') {
        Object.defineProperty(el, 'layoutSubtree', { value: true, configurable: true })
      }
      return el
    })

    expect(isLayoutSubtreeSupported()).toBe(true)
  })
})

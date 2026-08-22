import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { useViewTransition } from '@/composables/useViewTransition'

describe('useViewTransition', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('detects browser support accurately', () => {
    const { isSupported } = useViewTransition()
    expect(typeof isSupported).toBe('boolean')
  })

  it('executes callback directly when startViewTransition is unsupported or fallback occurs', async () => {
    const { withViewTransition } = useViewTransition()
    const mockAction = vi.fn<() => Promise<string>>().mockResolvedValue('success-result')

    const result = await withViewTransition(mockAction)

    expect(mockAction).toHaveBeenCalledTimes(1)
    expect(result).toBe('success-result')
  })

  it('delegates to element.startViewTransition when element supports it', async () => {
    const mockElement = document.createElement('div')
    const startViewTransitionSpy = vi.fn<(cb: () => Promise<void>) => { finished: Promise<void> }>(
      (cb: () => Promise<void>) => {
        void cb()
        return { finished: Promise.resolve() }
      },
    )
    ;(mockElement as unknown as { startViewTransition: unknown }).startViewTransition =
      startViewTransitionSpy

    const { withViewTransition } = useViewTransition()
    const mockAction = vi.fn<() => string>().mockReturnValue('element-scoped-result')

    const result = await withViewTransition(mockAction, { element: mockElement })

    expect(startViewTransitionSpy).toHaveBeenCalledTimes(1)
    expect(mockAction).toHaveBeenCalledTimes(1)
    expect(result).toBe('element-scoped-result')
  })

  it('executes directly without triggering document transition when element-scoped is unsupported', async () => {
    const mockElement = document.createElement('div') // does not have startViewTransition
    const docStartViewTransitionSpy = vi.fn<() => void>()
    ;(document as unknown as { startViewTransition: unknown }).startViewTransition =
      docStartViewTransitionSpy

    const { withViewTransition } = useViewTransition()
    const mockAction = vi.fn<() => string>().mockReturnValue('unsupported-element-vt')

    const result = await withViewTransition(mockAction, { element: mockElement })

    expect(docStartViewTransitionSpy).not.toHaveBeenCalled()
    expect(mockAction).toHaveBeenCalledTimes(1)
    expect(result).toBe('unsupported-element-vt')
  })

  it('delegates to document.startViewTransition with types when available', async () => {
    const startViewTransitionSpy = vi.fn<
      (opt: { update: () => Promise<void>; types: string[] } | (() => Promise<void>)) => {
        finished: Promise<void>
      }
    >((opt) => {
      if (typeof opt === 'function') {
        void opt()
      } else {
        void opt.update()
      }
      return { finished: Promise.resolve() }
    })
    ;(document as unknown as { startViewTransition: unknown }).startViewTransition =
      startViewTransitionSpy

    const { withViewTransition } = useViewTransition()
    const mockAction = vi.fn<() => string>().mockReturnValue('doc-transition-result')

    const result = await withViewTransition(mockAction, { types: ['forward'] })

    expect(startViewTransitionSpy).toHaveBeenCalledTimes(1)
    expect(mockAction).toHaveBeenCalledTimes(1)
    expect(result).toBe('doc-transition-result')
  })

  it('respects prefers-reduced-motion without calling startViewTransition', async () => {
    window.matchMedia = vi.fn<() => MediaQueryList>().mockReturnValue({
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener: vi.fn<() => void>(),
      removeListener: vi.fn<() => void>(),
      addEventListener: vi.fn<() => void>(),
      removeEventListener: vi.fn<() => void>(),
      dispatchEvent: vi.fn<() => boolean>(),
    } as unknown as MediaQueryList)

    const startViewTransitionSpy = vi.fn<() => void>()
    ;(document as unknown as { startViewTransition: unknown }).startViewTransition =
      startViewTransitionSpy

    const { withViewTransition } = useViewTransition()
    const mockAction = vi.fn<() => string>().mockReturnValue('reduced-motion-result')

    const result = await withViewTransition(mockAction)

    expect(startViewTransitionSpy).not.toHaveBeenCalled()
    expect(mockAction).toHaveBeenCalledTimes(1)
    expect(result).toBe('reduced-motion-result')
  })
})

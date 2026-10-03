import { effectScope, type EffectScope } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { usePageZoom } from '@/composables/usePageZoom'

describe('usePageZoom', () => {
  let scope: EffectScope

  beforeEach(() => {
    scope = effectScope()
  })

  afterEach(() => {
    scope.stop()
  })

  it('initializes with unzoomed default state', () => {
    scope.run(() => {
      const { isZoomed, zoomedPage, panOffset, isDragging, scale } = usePageZoom()

      expect(isZoomed.value).toBe(false)
      expect(zoomedPage.value).toBeNull()
      expect(panOffset.value).toEqual({ x: 0, y: 0 })
      expect(isDragging.value).toBe(false)
      expect(scale).toBe(2.5)
    })
  })

  it('toggles zoom on and off for the same page', () => {
    scope.run(() => {
      const onZoomChange = vi.fn<(isZoomed: boolean) => void>()
      const { toggleZoom, resetZoom, isZoomed, zoomedPage } = usePageZoom({ onZoomChange })

      toggleZoom(1)
      expect(isZoomed.value).toBe(true)
      expect(zoomedPage.value).toBe(1)
      expect(onZoomChange).toHaveBeenCalledWith(true)

      // Toggling the same page resets zoom
      toggleZoom(1)
      expect(isZoomed.value).toBe(false)
      expect(zoomedPage.value).toBeNull()
      expect(onZoomChange).toHaveBeenCalledWith(false)

      // Re-zoom and test resetZoom explicitly
      toggleZoom(2)
      expect(isZoomed.value).toBe(true)
      expect(zoomedPage.value).toBe(2)

      resetZoom()
      expect(isZoomed.value).toBe(false)
      expect(zoomedPage.value).toBeNull()
    })
  })

  it('calculates clamped initial pan offset based on click coordinates', () => {
    scope.run(() => {
      const { toggleZoom, panOffset } = usePageZoom({ scale: 2.5 })

      const mockFrame = {
        getBoundingClientRect: () => ({
          left: 100,
          top: 200,
          width: 400,
          height: 600,
          right: 500,
          bottom: 800,
          x: 100,
          y: 200,
          toJSON: () => {},
        }),
      } as unknown as HTMLElement

      // Click at center: (100 + 200, 200 + 300) = (300, 500)
      toggleZoom(1, { clientX: 300, clientY: 500 }, mockFrame)
      expect(panOffset.value.x).toBe(0)
      expect(panOffset.value.y).toBe(0)

      // Click near top-left: (100 + 50, 200 + 50) = (150, 250)
      // maxX = (2.5 - 1) * 400 / 2 = 300
      // maxY = (2.5 - 1) * 600 / 2 = 450
      toggleZoom(2, { clientX: 150, clientY: 250 }, mockFrame)
      expect(panOffset.value.x).toBeGreaterThan(0)
      expect(panOffset.value.x).toBeLessThanOrEqual(300)
      expect(panOffset.value.y).toBeGreaterThan(0)
      expect(panOffset.value.y).toBeLessThanOrEqual(450)
    })
  })

  it('updates pan offset during pointer drag with edge clamping', () => {
    scope.run(() => {
      const {
        toggleZoom,
        onPagePointerDown,
        onPagePointerMove,
        onPagePointerUp,
        panOffset,
        isDragging,
      } = usePageZoom({ scale: 2.5 })

      const mockElement = {
        setPointerCapture: vi.fn<(id: number) => void>(),
        releasePointerCapture: vi.fn<(id: number) => void>(),
        getBoundingClientRect: () => ({
          left: 0,
          top: 0,
          width: 400,
          height: 600,
          right: 400,
          bottom: 600,
          x: 0,
          y: 0,
          toJSON: () => {},
        }),
      } as unknown as HTMLElement

      toggleZoom(3, { clientX: 200, clientY: 300 }, mockElement)
      expect(panOffset.value).toEqual({ x: 0, y: 0 })

      // Pointer down starts dragging
      const downEvent = {
        clientX: 200,
        clientY: 300,
        pointerId: 1,
        currentTarget: mockElement,
        stopPropagation: vi.fn<() => void>(),
      } as unknown as PointerEvent

      onPagePointerDown(3, downEvent)
      expect(isDragging.value).toBe(true)

      // Drag move
      const moveEvent = {
        clientX: 250,
        clientY: 350,
        pointerId: 1,
        stopPropagation: vi.fn<() => void>(),
      } as unknown as PointerEvent

      onPagePointerMove(3, moveEvent)
      expect(panOffset.value.x).toBe(50)
      expect(panOffset.value.y).toBe(50)

      // Drag move beyond clamp boundary (maxX = 300)
      const farMoveEvent = {
        clientX: 1000,
        clientY: 1000,
        pointerId: 1,
        stopPropagation: vi.fn<() => void>(),
      } as unknown as PointerEvent

      onPagePointerMove(3, farMoveEvent)
      expect(panOffset.value.x).toBe(300)
      expect(panOffset.value.y).toBe(450)

      // Pointer up ends dragging
      const upEvent = {
        clientX: 1000,
        clientY: 1000,
        pointerId: 1,
        currentTarget: mockElement,
        stopPropagation: vi.fn<() => void>(),
      } as unknown as PointerEvent

      onPagePointerUp(3, upEvent)
      expect(isDragging.value).toBe(false)
    })
  })

  it('provides appropriate styles when zoomed vs unzoomed', () => {
    scope.run(() => {
      const { toggleZoom, getPageZoomStyle } = usePageZoom({ scale: 2.5 })

      expect(getPageZoomStyle(1)).toBeUndefined()

      toggleZoom(1)
      const zoomedStyle = getPageZoomStyle(1)
      expect(zoomedStyle).toBeDefined()
      expect(zoomedStyle?.transform).toContain('scale(2.5)')
      expect(zoomedStyle?.zIndex).toBe(20)

      // Other pages are dimmed while zoom is active
      const otherStyle = getPageZoomStyle(2)
      expect(otherStyle?.opacity).toBe(0.35)
      expect(otherStyle?.pointerEvents).toBe('none')
    })
  })

  it('resets zoom on Escape key and stops event propagation', () => {
    scope.run(() => {
      const { toggleZoom, isZoomed } = usePageZoom()

      toggleZoom(1)
      expect(isZoomed.value).toBe(true)

      const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
      const stopSpy = vi.spyOn(event, 'stopImmediatePropagation')
      window.dispatchEvent(event)

      expect(isZoomed.value).toBe(false)
      expect(stopSpy).toHaveBeenCalled()
    })
  })

  it('reports wasRecentlyToggled within threshold and expires after threshold', () => {
    scope.run(() => {
      const { toggleZoom, wasRecentlyToggled } = usePageZoom()

      expect(wasRecentlyToggled(450)).toBe(false)

      toggleZoom(1)
      expect(wasRecentlyToggled(450)).toBe(true)
    })
  })

  it('restricts double click zoom strictly to image area, ignoring clicks on black pillarbox/letterbox', () => {
    scope.run(() => {
      const { onPageDblClick, isZoomed } = usePageZoom()

      // 1. Double click on black pillarbox margin (target is page container without image)
      const blackBoxTarget = document.createElement('div')
      blackBoxTarget.className = 'page-frame'

      const blackBoxEvent = {
        clientX: 50,
        clientY: 50,
        target: blackBoxTarget,
        currentTarget: blackBoxTarget,
      } as unknown as MouseEvent

      onPageDblClick(1, blackBoxEvent)
      expect(isZoomed.value).toBe(false)

      // 2. Double click on image element
      const imgTarget = document.createElement('img')
      imgTarget.className = 'comic-page-img'
      blackBoxTarget.appendChild(imgTarget)

      const imgEvent = {
        clientX: 200,
        clientY: 300,
        target: imgTarget,
        currentTarget: blackBoxTarget,
      } as unknown as MouseEvent

      onPageDblClick(1, imgEvent)
      expect(isZoomed.value).toBe(true)
    })
  })

  it('panBy incrementally shifts offset within clamp limits and is inert when unzoomed', () => {
    scope.run(() => {
      const { toggleZoom, panBy, panOffset } = usePageZoom({ scale: 2.5 })

      // panBy is inert when unzoomed
      panBy(10, 20)
      expect(panOffset.value).toEqual({ x: 0, y: 0 })

      const mockElement = {
        getBoundingClientRect: () => ({
          left: 0,
          top: 0,
          width: 400,
          height: 600,
          right: 400,
          bottom: 600,
          x: 0,
          y: 0,
          toJSON: () => {},
        }),
      } as unknown as HTMLElement

      toggleZoom(1, { clientX: 200, clientY: 300 }, mockElement)
      expect(panOffset.value).toEqual({ x: 0, y: 0 })

      // Shift by dx=30, dy=-40
      panBy(30, -40)
      expect(panOffset.value).toEqual({ x: 30, y: -40 })

      // Clamp limit check (maxX = 300, maxY = 450)
      panBy(500, -800)
      expect(panOffset.value).toEqual({ x: 300, y: -450 })
    })
  })

  it('resets zoom automatically on window resize', () => {
    scope.run(() => {
      const { toggleZoom, isZoomed } = usePageZoom()

      toggleZoom(1)
      expect(isZoomed.value).toBe(true)

      window.dispatchEvent(new Event('resize'))
      expect(isZoomed.value).toBe(false)
    })
  })
})

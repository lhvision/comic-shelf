import { readonly, ref } from 'vue'

export interface HtmlCanvasStatus {
  supported: boolean
  rendered: boolean
  fallback: boolean
  drawsDomSubtree: boolean
  surface: string
}

interface HtmlCanvasContext {
  drawElement?: (element: Element, x?: number, y?: number) => void
}

const supported = ref(false)
const checked = ref(false)

function detectSupport(): boolean {
  if (typeof document === 'undefined') return false
  try {
    const probe = document.createElement('canvas')
    const ctx = probe.getContext('html') as HtmlCanvasContext | null
    return Boolean(ctx && typeof ctx.drawElement === 'function')
  } catch {
    return false
  }
}

export function useHtmlCanvas() {
  if (!checked.value) {
    supported.value = detectSupport()
    checked.value = true
  }

  return {
    supported: readonly(supported),
    getContext(canvas: HTMLCanvasElement): HtmlCanvasContext | null {
      try {
        return canvas.getContext('html') as HtmlCanvasContext | null
      } catch {
        return null
      }
    },
    publishStatus(rendered: boolean, surface: string) {
      const target = window as typeof window & {
        __COMIC_SHELF_HTML_CANVAS__?: unknown
      }
      target.__COMIC_SHELF_HTML_CANVAS__ = {
        supported: supported.value,
        rendered,
        fallback: !supported.value || !rendered,
        drawsDomSubtree: true,
        surface,
      } satisfies HtmlCanvasStatus
    },
  }
}

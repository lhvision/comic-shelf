/**
 * @file useReaderPip.ts
 * @description 桌面悬浮阅览窗（Document Picture-in-Picture API）生命周期与样式迁移组合式函数。
 *
 * 遵循 docs/JS_RADAR.md §3.10 与渐进增强契约：
 * - 仅在 Secure Context + 支持 `window.documentPictureInPicture` 的桌面端激活，其余环境静默隐藏；
 * - 一次性拷贝主文档 CSSStyleSheet（CORS 样式表自动回退为 `<link>`），保证暗室 Token 与 Scoped CSS 生效；
 * - 监听小窗 `pagehide` 与组件作用域销毁（`onScopeDispose`），防止路由离开后残留孤儿小窗。
 */

import { computed, onScopeDispose, ref, watch, type Ref } from 'vue'
import { useMediaQuery } from '@vueuse/core'

export interface UseReaderPipOptions {
  /** 外部受控的悬浮窗打开状态 Ref */
  open?: Ref<boolean>
  /** 当前作品标题（响应式，切换作品时同步更新悬浮窗标题栏） */
  title?: Ref<string | undefined>
  /** 当前画页是否处于放大态 */
  isZoomed?: Ref<boolean>
  /** 放大态复位回调（开启小窗前退出放大，避免双端状态混淆） */
  onResetZoom?: () => void
  /** 小窗成功打开后的回调 */
  onOpen?: () => void
  /** 小窗关闭并还原主窗后的回调 */
  onClose?: () => void
}

function formatPipTitle(title?: string): string {
  return title ? `${title} · 悬浮阅览` : '纸间 · 悬浮阅览窗'
}

function copyStylesToPipWindow(pipWindow: Window): void {
  const targetHead = pipWindow.document.head
  for (const styleSheet of Array.from(document.styleSheets)) {
    try {
      const cssText = Array.from(styleSheet.cssRules)
        .map((rule) => rule.cssText)
        .join('\n')
      const style = pipWindow.document.createElement('style')
      if (styleSheet.media.mediaText) {
        style.media = styleSheet.media.mediaText
      }
      style.textContent = cssText
      targetHead.appendChild(style)
    } catch {
      if (!styleSheet.href) continue
      const link = pipWindow.document.createElement('link')
      link.rel = 'stylesheet'
      link.href = styleSheet.href
      if (styleSheet.media.mediaText) {
        link.media = styleSheet.media.mediaText
      }
      targetHead.appendChild(link)
    }
  }

  const baseStyle = pipWindow.document.createElement('style')
  baseStyle.textContent = `
    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100dvh;
      overflow: hidden;
      background: var(--reader-bg, #0d0e0c);
      color: var(--reader-ink, #eee7da);
      font-family: var(--font-body, system-ui, sans-serif);
    }
  `
  targetHead.appendChild(baseStyle)
}

/**
 * 桌面悬浮阅览窗组合式函数
 * @param options 生命周期与联动选项
 */
export function useReaderPip(options: UseReaderPipOptions = {}) {
  const { open, title, isZoomed, onResetZoom, onOpen, onClose } = options

  const isCoarsePointer = useMediaQuery('(pointer: coarse)')
  const isPipSupported = computed(
    () =>
      typeof window !== 'undefined' &&
      Boolean(window.isSecureContext) &&
      'documentPictureInPicture' in window &&
      typeof window.documentPictureInPicture?.requestWindow === 'function' &&
      !isCoarsePointer.value,
  )

  const isPipOpen = open ?? ref(false)
  const pipMountTarget = ref<HTMLElement | null>(null)
  let pipWindowRef: Window | null = null
  let openingPromise: Promise<boolean> | null = null
  let isDisposed = false

  function cleanupPipState(triggerCloseCallback: boolean): void {
    const wasOpen = isPipOpen.value || pipMountTarget.value !== null || pipWindowRef !== null
    isPipOpen.value = false
    pipMountTarget.value = null
    pipWindowRef = null
    if (wasOpen && triggerCloseCallback) {
      onClose?.()
    }
  }

  function handlePipPageHide(): void {
    cleanupPipState(true)
  }

  function teardownPipWindow(triggerCloseCallback: boolean): void {
    const win = pipWindowRef
    if (win) {
      win.removeEventListener('pagehide', handlePipPageHide)
    }
    cleanupPipState(triggerCloseCallback)
    if (win && !win.closed) {
      try {
        win.close()
      } catch {
        // ignore close failure
      }
    }
  }

  async function openPip(overrideTitle?: string): Promise<boolean> {
    if (isDisposed || !isPipSupported.value) return false

    if (pipWindowRef && !pipWindowRef.closed) {
      pipWindowRef.focus()
      return true
    }

    if (openingPromise) {
      return openingPromise
    }

    if (isZoomed?.value) {
      onResetZoom?.()
    }

    const task = (async () => {
      try {
        const pipApi = window.documentPictureInPicture
        if (!pipApi) return false

        const pipWindow = await pipApi.requestWindow({
          width: 440,
          height: 640,
        })

        // 若等待窗口授权期间作用域已销毁，立即关闭刚打开的孤儿窗口
        if (isDisposed) {
          try {
            pipWindow.close()
          } catch {
            // ignore close failure
          }
          return false
        }

        pipWindow.document.documentElement.lang = document.documentElement.lang || 'zh-CN'
        pipWindow.document.title = formatPipTitle(overrideTitle ?? title?.value)
        copyStylesToPipWindow(pipWindow)

        const container = pipWindow.document.createElement('div')
        container.id = 'paper-room-pip-root'
        container.style.cssText = 'width: 100%; height: 100%;'
        pipWindow.document.body.replaceChildren(container)

        pipWindowRef = pipWindow
        pipMountTarget.value = container
        isPipOpen.value = true

        pipWindow.addEventListener('pagehide', handlePipPageHide, { once: true })
        onOpen?.()
        return true
      } catch {
        cleanupPipState(false)
        return false
      } finally {
        openingPromise = null
      }
    })()

    openingPromise = task
    return task
  }

  function closePip(): void {
    teardownPipWindow(true)
  }

  async function togglePip(overrideTitle?: string): Promise<void> {
    if (isPipOpen.value) {
      closePip()
    } else {
      await openPip(overrideTitle)
    }
  }

  if (title) {
    watch(title, (newTitle) => {
      if (isPipOpen.value && pipWindowRef && !pipWindowRef.closed) {
        pipWindowRef.document.title = formatPipTitle(newTitle)
      }
    })
  }

  onScopeDispose(() => {
    isDisposed = true
    teardownPipWindow(false)
  })

  return {
    isPipSupported,
    isPipOpen,
    pipMountTarget,
    openPip,
    closePip,
    togglePip,
  }
}

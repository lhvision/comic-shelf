/**
 * @file useReaderKeyboard.ts
 * @description 阅读器全屏切换与全功能键盘热键映射组合式函数。
 *
 * 热键映射表：
 * - `ArrowRight` / `ArrowLeft`：根据排版模式与 LTR/RTL 阅读方向自适应上一屏 / 下一屏；
 * - `ArrowDown` / `PageDown` / `Space`：下一屏；
 * - `ArrowUp` / `PageUp`：上一屏；
 * - `Home`：跳转到本话/全书第 1 页；
 * - `End`：跳转到本话/全书最后一页；
 * - `N` / `n`：跳到下一话；
 * - `P` / `p`：跳到上一话；
 * - `F` / `f`：一键全屏 / 退出全屏（通过 VueUse `useFullscreen` 接管）；
 * - `T` / `t` 或 `S` / `s`：展开 / 收起微缩胶卷预览轨（Filmstrip Scrubber）；
 * - `Escape`：若设置面板展开则关闭设置面板，若胶片轨展开则收起胶片轨，否则返回作品详情页。
 */

import type { ComputedRef, Ref } from 'vue'
import { useEventListener, useFullscreen } from '@vueuse/core'
import type { ReaderSettings } from '@/composables/useReaderSettings'

/**
 * `useReaderKeyboard` 初始化配置依赖
 */
export interface UseReaderKeyboardOptions {
  /** 设置面板显隐状态 Ref */
  settingsOpen: Ref<boolean>
  /** 胶片预览轨显隐状态 Ref */
  filmstripOpen?: Ref<boolean>
  /** 切换胶片预览轨显隐回调 */
  toggleFilmstrip?: () => void
  /** 阅读器设置（用于判断横纵向与 RTL 翻页方向） */
  settings: ReaderSettings
  /** 当前作用域总页数 */
  total: ComputedRef<number>
  /** 跳转指定页回调 */
  goToPage: (page: number) => void
  /** 上一屏翻页回调 */
  prevGroup: (behavior?: ScrollBehavior) => void
  /** 下一屏翻页回调 */
  nextGroup: (behavior?: ScrollBehavior) => void
  /** 下一话跳转回调 */
  goNextChapter: () => void
  /** 上一话跳转回调 */
  goPrevChapter: () => void
  /** 返回详情页回调 */
  backToDetail: () => void
  /** 用户主动键盘翻阅交互通知 */
  onUserInteract?: () => void
  /** 连续按键释放通知（用于延长静默锁定） */
  onKeyRelease?: () => void
}

/**
 * 阅读器键盘热键与全屏 Hook
 * @param options 配置依赖
 */
export function useReaderKeyboard(options: UseReaderKeyboardOptions) {
  const {
    settingsOpen,
    filmstripOpen,
    toggleFilmstrip,
    settings,
    total,
    goToPage,
    prevGroup,
    nextGroup,
    goNextChapter,
    goPrevChapter,
    backToDetail,
    onUserInteract,
    onKeyRelease,
  } = options

  /** 通过 VueUse useFullscreen 控制 root HTML 元素全屏 */
  const { toggle: toggleFullscreen } = useFullscreen(
    typeof document !== 'undefined' ? document.documentElement : undefined,
  )

  let lastRepeatTime = 0
  const REPEAT_THROTTLE_MS = 110

  /** 全局 keydown 键盘事件处理分发器 */
  function onKeydown(event: KeyboardEvent) {
    // 忽略表单输入元素内部的键盘敲击
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
      return
    }
    if (event.target instanceof HTMLSelectElement) return

    // 忽略带修饰键的组合键（Ctrl / Cmd / Alt），避免劫持浏览器原生快捷键（如 Ctrl+S / Ctrl+T / Ctrl+F 等）
    if (event.ctrlKey || event.metaKey || event.altKey) {
      return
    }

    // 1. 设置面板打开时，ESC 优先关闭面板
    if (settingsOpen.value) {
      if (event.key === 'Escape') {
        event.preventDefault()
        settingsOpen.value = false
      }
      return
    }

    // 2. 胶片预览轨打开时，ESC 优先收起胶卷抽屉
    if (filmstripOpen?.value && event.key === 'Escape') {
      event.preventDefault()
      filmstripOpen.value = false
      return
    }

    const isNavKey = [
      'ArrowRight',
      'ArrowLeft',
      'ArrowDown',
      'ArrowUp',
      'PageDown',
      'PageUp',
      ' ',
    ].includes(event.key)

    // 键盘长按节流：无论初次敲击还是操作系统连续连击，均统一以 110ms 进行节奏节流
    if (isNavKey) {
      const now = performance.now()
      if (event.repeat && now - lastRepeatTime < REPEAT_THROTTLE_MS) {
        event.preventDefault()
        return
      }
      lastRepeatTime = now
    }

    const rtl = settings.mode === 'horizontal' && settings.direction === 'rtl'
    const nextLeft = rtl
    // 长按连击期间采用 'auto'（即时）以杜绝多重 smooth 动画累积与排队滞后，单次点击采用 'smooth'
    const behavior: ScrollBehavior = event.repeat ? 'auto' : 'smooth'

    switch (event.key) {
      case 'ArrowRight':
        event.preventDefault()
        onUserInteract?.()
        if (nextLeft) prevGroup(behavior)
        else nextGroup(behavior)
        break
      case 'ArrowLeft':
        event.preventDefault()
        onUserInteract?.()
        if (nextLeft) nextGroup(behavior)
        else prevGroup(behavior)
        break
      case 'ArrowDown':
      case 'PageDown':
      case ' ':
        event.preventDefault()
        onUserInteract?.()
        nextGroup(behavior)
        break
      case 'ArrowUp':
      case 'PageUp':
        event.preventDefault()
        onUserInteract?.()
        prevGroup(behavior)
        break
      case 'Home':
        event.preventDefault()
        onUserInteract?.()
        goToPage(1)
        break
      case 'End':
        event.preventDefault()
        onUserInteract?.()
        goToPage(total.value)
        break
      case 'n':
      case 'N':
        onUserInteract?.()
        goNextChapter()
        break
      case 'p':
      case 'P':
        onUserInteract?.()
        goPrevChapter()
        break
      case 'f':
      case 'F':
        void toggleFullscreen()
        break
      case 't':
      case 'T':
      case 's':
      case 'S':
        onUserInteract?.()
        toggleFilmstrip?.()
        break
      case 'Escape':
        event.preventDefault()
        backToDetail()
        break
    }
  }

  function onKeyup(event: KeyboardEvent) {
    if (
      ['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', ' '].includes(
        event.key,
      )
    ) {
      onKeyRelease?.()
    }
  }

  // 绑定全局键盘监听并在组件卸载时自动注销
  useEventListener(typeof window !== 'undefined' ? window : null, 'keydown', onKeydown)
  useEventListener(typeof window !== 'undefined' ? window : null, 'keyup', onKeyup)

  return {
    toggleFullscreen,
    onKeydown,
    onKeyup,
  }
}

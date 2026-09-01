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
 * - `Escape`：若设置面板展开则关闭设置面板，否则返回作品详情页。
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
  /** 阅读器设置（用于判断横纵向与 RTL 翻页方向） */
  settings: ReaderSettings
  /** 当前作用域总页数 */
  total: ComputedRef<number>
  /** 跳转指定页回调 */
  goToPage: (page: number) => void
  /** 上一屏翻页回调 */
  prevGroup: () => void
  /** 下一屏翻页回调 */
  nextGroup: () => void
  /** 下一话跳转回调 */
  goNextChapter: () => void
  /** 上一话跳转回调 */
  goPrevChapter: () => void
  /** 返回详情页回调 */
  backToDetail: () => void
}

/**
 * 阅读器键盘热键与全屏 Hook
 * @param options 配置依赖
 */
export function useReaderKeyboard(options: UseReaderKeyboardOptions) {
  const {
    settingsOpen,
    settings,
    total,
    goToPage,
    prevGroup,
    nextGroup,
    goNextChapter,
    goPrevChapter,
    backToDetail,
  } = options

  /** 通过 VueUse useFullscreen 控制 root HTML 元素全屏 */
  const { toggle: toggleFullscreen } = useFullscreen(
    typeof document !== 'undefined' ? document.documentElement : undefined,
  )

  /** 全局 keydown 键盘事件处理分发器 */
  function onKeydown(event: KeyboardEvent) {
    // 忽略表单输入元素内部的键盘敲击
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
      return
    }
    if (event.target instanceof HTMLSelectElement) return

    // 设置面板打开时，ESC 优先关闭面板
    if (settingsOpen.value) {
      if (event.key === 'Escape') {
        event.preventDefault()
        settingsOpen.value = false
      }
      return
    }

    const rtl = settings.mode === 'horizontal' && settings.direction === 'rtl'
    const nextLeft = rtl

    switch (event.key) {
      case 'ArrowRight':
        event.preventDefault()
        if (nextLeft) prevGroup()
        else nextGroup()
        break
      case 'ArrowLeft':
        event.preventDefault()
        if (nextLeft) nextGroup()
        else prevGroup()
        break
      case 'ArrowDown':
      case 'PageDown':
      case ' ':
        event.preventDefault()
        nextGroup()
        break
      case 'ArrowUp':
      case 'PageUp':
        event.preventDefault()
        prevGroup()
        break
      case 'Home':
        event.preventDefault()
        goToPage(1)
        break
      case 'End':
        event.preventDefault()
        goToPage(total.value)
        break
      case 'n':
      case 'N':
        goNextChapter()
        break
      case 'p':
      case 'P':
        goPrevChapter()
        break
      case 'f':
      case 'F':
        void toggleFullscreen()
        break
      case 'Escape':
        event.preventDefault()
        backToDetail()
        break
    }
  }

  // 绑定全局键盘监听并在组件卸载时自动注销
  useEventListener(typeof window !== 'undefined' ? window : null, 'keydown', onKeydown)

  return {
    toggleFullscreen,
    onKeydown,
  }
}

/**
 * @file useReaderBoundaryOverscroll.ts
 * @description 纵向排版（连续/翻页）触底上拉、贴顶下拉与滚轮超拉自动跨章节状态机。
 *
 * 从 `useReaderNavigation.ts` 拆出，独立维护边缘停留判定、惯性防抖窗口、切话冷却与触控位移追踪。
 */

import type { ComputedRef, Ref } from 'vue'
import type { Chapter } from '@/types'
import type { ReaderSettings } from '@/composables/useReaderSettings'

export interface UseReaderBoundaryOverscrollOptions {
  scrollEl: Ref<HTMLElement | null>
  settings: ReaderSettings
  nextChapter: ComputedRef<Chapter | null>
  prevChapter: ComputedRef<Chapter | null>
  isSwitchingChapter: Ref<boolean>
  goNextChapter: () => void
  goPrevChapter: () => void
}

const BOUNDARY_SETTLE_MS = 220
const BOUNDARY_COOLDOWN_MS = 350
const OVERSCROLL_THRESHOLD = 80
const TOUCH_OVERSCROLL_PX = 48

/** 判定容器是否已到达可触发向下一话跨话的底端边缘 */
export function isAtScrollBottom(el: HTMLElement): boolean {
  if (el.clientHeight <= 0 || el.scrollHeight <= 0) return false
  return (
    el.scrollHeight <= el.clientHeight + 24 ||
    el.scrollTop + el.clientHeight >= el.scrollHeight - 24
  )
}

/** 判定容器是否已到达可触发向上一话跨话的顶端边缘 */
export function isAtScrollTop(el: HTMLElement): boolean {
  return el.scrollTop <= 16
}

/**
 * 纵向边界超拉自动跨话检测器
 * @param options 容器、章节上下文与切话回调
 */
export function useReaderBoundaryOverscroll(options: UseReaderBoundaryOverscrollOptions) {
  const {
    scrollEl,
    settings,
    nextChapter,
    prevChapter,
    isSwitchingChapter,
    goNextChapter,
    goPrevChapter,
  } = options

  let wasAtBottom = false
  let wasAtTop = true
  let bottomReachedAt = 0
  let topReachedAt = 0
  let boundaryCooldownUntil = 0
  let overscrollDelta = 0
  let overscrollDirection: 'next' | 'prev' | null = null
  let overscrollResetTimer: ReturnType<typeof setTimeout> | null = null
  let touchStartY: number | null = null
  let touchStartedAtBottom = false
  let touchStartedAtTop = false

  function resetOverscroll() {
    overscrollDelta = 0
    overscrollDirection = null
    if (overscrollResetTimer !== null) {
      clearTimeout(overscrollResetTimer)
      overscrollResetTimer = null
    }
  }

  /** 切话后重置边界锚点，并把最早可触发稳定期推迟至冷却结束后 */
  function resetBoundaryTrackers() {
    resetOverscroll()
    const now = performance.now()
    boundaryCooldownUntil = now + BOUNDARY_COOLDOWN_MS
    bottomReachedAt = boundaryCooldownUntil
    topReachedAt = boundaryCooldownUntil
    wasAtBottom = false
    wasAtTop = false
    touchStartY = null
    touchStartedAtBottom = false
    touchStartedAtTop = false
  }

  /** 在滚动帧中更新贴顶/触底首次抵达时间戳 */
  function recordScrollEdges(el: HTMLElement) {
    const now = performance.now()
    const atBottom = isAtScrollBottom(el)
    if (atBottom && !wasAtBottom) {
      bottomReachedAt = Math.max(now, boundaryCooldownUntil)
    }
    wasAtBottom = atBottom

    const atTop = isAtScrollTop(el)
    if (atTop && !wasAtTop) {
      topReachedAt = Math.max(now, boundaryCooldownUntil)
    }
    wasAtTop = atTop
  }

  /** 处理纵向排版下的滚轮超拉跨话；若命中跨话条件返回 true */
  function handleVerticalWheel(event: WheelEvent, el: HTMLElement, normalizedDeltaY: number) {
    const now = performance.now()
    if (now < boundaryCooldownUntil) {
      resetOverscroll()
      return
    }

    const dir = normalizedDeltaY > 0 ? 'next' : normalizedDeltaY < 0 ? 'prev' : null
    const atTargetEdge =
      dir === 'next'
        ? Boolean(nextChapter.value) && isAtScrollBottom(el)
        : dir === 'prev'
          ? Boolean(prevChapter.value) && isAtScrollTop(el)
          : false
    const reachedAt = dir === 'next' ? bottomReachedAt : topReachedAt

    if (dir && atTargetEdge) {
      if (now - reachedAt < BOUNDARY_SETTLE_MS) return
      if (overscrollDirection !== dir) {
        overscrollDelta = 0
        overscrollDirection = dir
      }
      overscrollDelta += Math.abs(normalizedDeltaY)
      if (overscrollResetTimer !== null) clearTimeout(overscrollResetTimer)
      overscrollResetTimer = setTimeout(resetOverscroll, 450)
      if (overscrollDelta >= OVERSCROLL_THRESHOLD) {
        event.preventDefault()
        resetOverscroll()
        if (dir === 'next') goNextChapter()
        else goPrevChapter()
      }
      return
    }

    resetOverscroll()
  }

  /** 记录触屏起始边界，供松手时判定贴底上拉 / 贴顶下拉自动跨话 */
  function onViewportTouchStart(event: TouchEvent) {
    const el = scrollEl.value
    const touch = event.touches?.[0]
    if (!el || !touch || settings.mode === 'horizontal') {
      touchStartY = null
      return
    }
    touchStartY = touch.clientY
    touchStartedAtBottom = isAtScrollBottom(el)
    touchStartedAtTop = isAtScrollTop(el)
  }

  /** 触屏贴底上拉 / 贴顶下拉释放时触发自动切话 */
  function onViewportTouchEnd(event: TouchEvent) {
    const el = scrollEl.value
    const touch = event.changedTouches?.[0]
    const startY = touchStartY
    const startedAtBottom = touchStartedAtBottom
    const startedAtTop = touchStartedAtTop
    touchStartY = null
    touchStartedAtBottom = false
    touchStartedAtTop = false

    if (!el || !touch || startY === null || settings.mode === 'horizontal') return
    if (isSwitchingChapter.value) return

    const now = performance.now()
    if (now < boundaryCooldownUntil) return

    const swipeDelta = startY - touch.clientY
    const dir = swipeDelta > 0 ? 'next' : swipeDelta < 0 ? 'prev' : null
    if (!dir || Math.abs(swipeDelta) < TOUCH_OVERSCROLL_PX) return

    if (
      dir === 'next' &&
      startedAtBottom &&
      nextChapter.value &&
      isAtScrollBottom(el) &&
      now - bottomReachedAt >= BOUNDARY_SETTLE_MS
    ) {
      goNextChapter()
    } else if (
      dir === 'prev' &&
      startedAtTop &&
      prevChapter.value &&
      isAtScrollTop(el) &&
      now - topReachedAt >= BOUNDARY_SETTLE_MS
    ) {
      goPrevChapter()
    }
  }

  return {
    resetOverscroll,
    resetBoundaryTrackers,
    recordScrollEdges,
    handleVerticalWheel,
    onViewportTouchStart,
    onViewportTouchEnd,
  }
}

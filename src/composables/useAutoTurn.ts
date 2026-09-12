/**
 * @file useAutoTurn.ts
 * @description 阅读器自动阅读状态机（离散定时翻页与条漫匀速流卷双轨架构）。
 *
 * 核心职责：
 * 1. 翻页模式（竖向翻页 / 横向翻页）：按固定秒数（`autoTurnInterval`）倒计时推进分屏；
 * 2. 连续模式（竖向连续条漫）：基于 `requestAnimationFrame` 以 `autoScrollSpeed` (px/s) 匀速推进物理视口；
 * 3. 交互瞬时避让（Soft Yield）：读者手动操作（触控/滚轮）时自动流卷暂避 1.5s，静止后平滑恢复；
 * 4. 话末平缓停靠（Dock & Hold）：流卷抵达当前话底端时自动驻留刹车，等待读者确认；
 * 5. 页面可见性与设置面板联动：退火切后台或打开设置面板时即刻挂起。
 */

import {
  computed,
  getCurrentScope,
  onScopeDispose,
  ref,
  toValue,
  watch,
  type ComputedRef,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'
import { useDocumentVisibility, useIntervalFn, useTimeoutFn } from '@vueuse/core'
import type { ReaderSettings } from '@/composables/useReaderSettings'

export interface UseAutoTurnOptions {
  /** 阅读器设置对象（模式、翻页秒数、流卷速度等） */
  settings: MaybeRefOrGetter<ReaderSettings> | ReaderSettings
  /** 当前分屏分组索引 Ref */
  currentGroupIndex: Ref<number>
  /** 最后一组分屏索引 ComputedRef */
  lastGroupIndex: ComputedRef<number>
  /** 设置面板是否处于打开态 Ref */
  settingsOpen: Ref<boolean>
  /** 顶栏与悬浮控制栏是否处于展开可见态 Ref */
  chromeVisible?: Ref<boolean>
  /** 离散翻页步进回调 */
  onAdvance: () => void
  /** 顶栏唤醒隐藏调度回调 */
  onScheduleChromeHide?: () => void
  /** 阅读器滚动容器 DOM Ref（连续模式流卷所必需） */
  scrollEl?: Ref<HTMLElement | null>
}

/**
 * 阅读器自动阅读组合式函数
 * @param options 配置依赖
 */
export function useAutoTurn(options: UseAutoTurnOptions) {
  const {
    settings,
    currentGroupIndex,
    lastGroupIndex,
    settingsOpen,
    chromeVisible,
    onAdvance,
    onScheduleChromeHide,
    scrollEl,
  } = options

  const currentSettings = computed(() => toValue(settings))
  const autoTurnRemaining = ref(currentSettings.value.autoTurnInterval)
  const autoTurnPaused = ref(false)
  const isYielding = ref(false)
  const isDockedAtEnd = ref(false)
  const documentVisibility = useDocumentVisibility()

  // ---------------- 1. 离散翻页模式判定与定时器 ----------------
  function canAutoTurnRun() {
    return (
      currentSettings.value.autoTurn &&
      currentSettings.value.mode !== 'vertical-continuous' &&
      !autoTurnPaused.value &&
      !settingsOpen.value &&
      documentVisibility.value === 'visible' &&
      currentGroupIndex.value < lastGroupIndex.value
    )
  }

  const { pause: pauseAutoTurnTick, resume: resumeAutoTurnTick } = useIntervalFn(
    () => {
      autoTurnRemaining.value -= 1
      if (autoTurnRemaining.value > 0) return

      if (!canAutoTurnRun()) {
        stopAutoTurnCountdown()
        return
      }
      onAdvance()
      startAutoTurnCountdown()
    },
    1000,
    { immediate: false },
  )

  function startAutoTurnCountdown() {
    pauseAutoTurnTick()
    if (!canAutoTurnRun()) {
      autoTurnRemaining.value = currentSettings.value.autoTurnInterval
      return
    }
    autoTurnRemaining.value = currentSettings.value.autoTurnInterval
    resumeAutoTurnTick()
  }

  function stopAutoTurnCountdown() {
    pauseAutoTurnTick()
    autoTurnRemaining.value = currentSettings.value.autoTurnInterval
  }

  function resetAutoTurnCountdown() {
    if (!currentSettings.value.autoTurn) return
    isDockedAtEnd.value = false

    if (currentSettings.value.mode === 'vertical-continuous') {
      if (!autoTurnPaused.value && !isYielding.value) {
        startAutoScroll()
      }
      return
    }

    if (autoTurnPaused.value) return
    startAutoTurnCountdown()
  }

  // ---------------- 2. 连续条漫模式匀速流卷（rAF）与避让 ----------------
  let rafId: number | null = null
  let lastTimestamp = 0
  let lastExpectedScrollTop = -1

  function canAutoScrollRun() {
    if (!currentSettings.value.autoTurn || currentSettings.value.mode !== 'vertical-continuous') {
      return false
    }
    if (
      autoTurnPaused.value ||
      isDockedAtEnd.value ||
      isYielding.value ||
      settingsOpen.value ||
      chromeVisible?.value
    ) {
      return false
    }
    if (documentVisibility.value !== 'visible') {
      return false
    }
    const el = scrollEl?.value
    if (!el) return false
    const max = el.scrollHeight - el.clientHeight
    if (max > 0 && el.scrollTop >= max - 2) {
      return false
    }
    return true
  }

  function tickScroll(timestamp: number) {
    if (!lastTimestamp) lastTimestamp = timestamp
    const deltaMs = Math.min(64, timestamp - lastTimestamp)
    lastTimestamp = timestamp

    const el = scrollEl?.value
    if (el && lastExpectedScrollTop >= 0 && Math.abs(el.scrollTop - lastExpectedScrollTop) > 28) {
      // 读者通过原生滚动条拖拽或大幅手势发生了外部位移，触发软避让
      lastExpectedScrollTop = el.scrollTop
      yieldAutoScroll()
    }

    if (canAutoScrollRun()) {
      if (el) {
        const speed = currentSettings.value.autoScrollSpeed || 80
        const step = (speed * deltaMs) / 1000
        const max = el.scrollHeight - el.clientHeight
        const target = Math.min(max, el.scrollTop + step)
        el.scrollTop = target
        lastExpectedScrollTop = target

        // 到达话末：平缓停靠，等待读者主动切话
        if (target >= max - 2) {
          stopAutoScroll()
          isDockedAtEnd.value = true
          return
        }
      }
    }

    if (
      currentSettings.value.mode === 'vertical-continuous' &&
      currentSettings.value.autoTurn &&
      !autoTurnPaused.value &&
      !isDockedAtEnd.value &&
      Boolean(scrollEl?.value)
    ) {
      rafId = requestAnimationFrame(tickScroll)
    } else {
      rafId = null
      lastTimestamp = 0
    }
  }

  function startAutoScroll() {
    if (rafId !== null) return
    if (!currentSettings.value.autoTurn || autoTurnPaused.value || isDockedAtEnd.value) {
      return
    }
    lastTimestamp = 0
    rafId = requestAnimationFrame(tickScroll)
  }

  function stopAutoScroll() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    lastTimestamp = 0
  }

  /** 瞬时避让定时器：读者触控/滚轮交互后静待 1.5s 平滑恢复 */
  const { start: startYieldTimer, stop: stopYieldTimer } = useTimeoutFn(
    () => {
      isYielding.value = false
      if (
        currentSettings.value.mode === 'vertical-continuous' &&
        currentSettings.value.autoTurn &&
        !autoTurnPaused.value
      ) {
        startAutoScroll()
      }
    },
    1500,
    { immediate: false },
  )

  /** 供视图层在用户主动交互（滚轮、拖拽、触控）时调用 */
  function yieldAutoScroll() {
    if (currentSettings.value.mode !== 'vertical-continuous' || !currentSettings.value.autoTurn) {
      return
    }
    // 若读者已从话末底端向上回滚离开（重新查阅前文），解除驻留锁以允许恢复流卷
    const el = scrollEl?.value
    if (el && isDockedAtEnd.value) {
      const max = el.scrollHeight - el.clientHeight
      if (max > 0 && el.scrollTop < max - 40) {
        isDockedAtEnd.value = false
      }
    }
    isYielding.value = true
    stopYieldTimer()
    startYieldTimer()
  }

  // ---------------- 3. 控制与状态切换 ----------------
  function toggleAutoTurnPause() {
    if (!currentSettings.value.autoTurn || settingsOpen.value) {
      return
    }
    if (
      currentSettings.value.mode !== 'vertical-continuous' &&
      currentGroupIndex.value >= lastGroupIndex.value
    ) {
      return
    }

    if (isDockedAtEnd.value) {
      isDockedAtEnd.value = false
    }

    autoTurnPaused.value = !autoTurnPaused.value
    if (autoTurnPaused.value) {
      pauseAutoTurnTick()
      stopAutoScroll()
    } else {
      isYielding.value = false
      stopYieldTimer()
      if (currentSettings.value.mode === 'vertical-continuous') {
        startAutoScroll()
      } else {
        resetAutoTurnCountdown()
      }
    }
  }

  function restartActiveRunner() {
    stopAutoScroll()
    stopAutoTurnCountdown()
    isYielding.value = false
    stopYieldTimer()

    if (!currentSettings.value.autoTurn) return
    autoTurnPaused.value = false

    if (currentSettings.value.mode === 'vertical-continuous') {
      startAutoScroll()
    } else {
      startAutoTurnCountdown()
    }
  }

  watch(
    () => [currentSettings.value.autoTurn, currentSettings.value.mode] as const,
    () => {
      restartActiveRunner()
    },
  )

  watch(
    () => currentSettings.value.autoTurnInterval,
    () => {
      if (currentSettings.value.mode !== 'vertical-continuous') {
        resetAutoTurnCountdown()
      }
    },
  )

  watch(
    () => currentSettings.value.autoScrollSpeed,
    () => {
      if (currentSettings.value.mode === 'vertical-continuous' && currentSettings.value.autoTurn) {
        startAutoScroll()
      }
    },
  )

  watch(settingsOpen, (open) => {
    if (open) {
      pauseAutoTurnTick()
      stopAutoScroll()
    } else {
      onScheduleChromeHide?.()
      if (currentSettings.value.mode === 'vertical-continuous') {
        if (currentSettings.value.autoTurn && !autoTurnPaused.value) {
          startAutoScroll()
        }
      } else {
        resetAutoTurnCountdown()
      }
    }
  })

  watch(documentVisibility, (state) => {
    if (state === 'hidden') {
      pauseAutoTurnTick()
      stopAutoScroll()
    } else if (currentSettings.value.mode === 'vertical-continuous') {
      if (currentSettings.value.autoTurn && !autoTurnPaused.value) {
        startAutoScroll()
      }
    } else {
      resetAutoTurnCountdown()
    }
  })

  if (chromeVisible) {
    watch(chromeVisible, (visible) => {
      if (currentSettings.value.mode !== 'vertical-continuous') return
      if (visible) {
        stopAutoScroll()
      } else if (
        currentSettings.value.autoTurn &&
        !autoTurnPaused.value &&
        !isYielding.value &&
        !settingsOpen.value
      ) {
        startAutoScroll()
      }
    })
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      stopAutoScroll()
      stopAutoTurnCountdown()
      stopYieldTimer()
    })
  }

  return {
    autoTurnRemaining,
    autoTurnPaused,
    isYielding,
    isDockedAtEnd,
    canAutoTurnRun,
    startAutoTurnCountdown,
    stopAutoTurnCountdown,
    resetAutoTurnCountdown,
    startAutoScroll,
    stopAutoScroll,
    yieldAutoScroll,
    toggleAutoTurnPause,
  }
}

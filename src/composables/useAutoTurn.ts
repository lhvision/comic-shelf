/**
 * @file useAutoTurn.ts
 * @description 阅读器自动切换状态机（离散翻页排版模式专享）。
 *
 * 核心职责：
 * 1. 离散翻页模式（竖向翻页 / 横向翻页）：按固定秒数（`autoTurnInterval`）倒计时推进分屏；
 * 2. 竖向连续长卷（条漫）：天生由读者指尖/滚轮 1:1 掌控阅读节奏，设计上彻底豁免自动化以杜绝动晕症与失控感；
 * 3. 100% 画面静止保障：倒计时期间视口绝对静止，仅在切页瞬间推进；
 * 4. 交互自愈重置：读者手动操作（触控/滚轮/按键）时无感重置倒计时，重续阅读心流；
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
import { useDocumentVisibility, useIntervalFn } from '@vueuse/core'
import type { ReaderSettings } from '@/composables/useReaderSettings'

export interface UseAutoTurnOptions {
  /** 阅读器设置对象（模式、翻页秒数等） */
  settings: MaybeRefOrGetter<ReaderSettings> | ReaderSettings
  /** 当前分屏分组索引 Ref */
  currentGroupIndex: Ref<number>
  /** 最后一组分屏索引 ComputedRef */
  lastGroupIndex: ComputedRef<number>
  /** 设置面板是否处于打开态 Ref */
  settingsOpen: Ref<boolean>
  /** 顶栏与悬浮控制栏是否处于展开可见态 Ref */
  chromeVisible?: Ref<boolean>
  /** 自动翻页推进回调 */
  onAdvance: () => void
  /** 顶栏唤醒隐藏调度回调 */
  onScheduleChromeHide?: () => void
}

/**
 * 阅读器自动切换组合式函数
 * @param options 配置依赖
 */
export function useAutoTurn(options: UseAutoTurnOptions) {
  const {
    settings,
    currentGroupIndex,
    lastGroupIndex,
    settingsOpen,
    onAdvance,
    onScheduleChromeHide,
  } = options

  const currentSettings = computed(() => toValue(settings))
  const autoTurnRemaining = ref(currentSettings.value.autoTurnInterval)
  const autoTurnPaused = ref(false)
  const documentVisibility = useDocumentVisibility()

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
    if (!currentSettings.value.autoTurn || currentSettings.value.mode === 'vertical-continuous') {
      stopAutoTurnCountdown()
      return
    }
    if (autoTurnPaused.value) return
    startAutoTurnCountdown()
  }

  function toggleAutoTurnPause() {
    if (
      !currentSettings.value.autoTurn ||
      currentSettings.value.mode === 'vertical-continuous' ||
      settingsOpen.value ||
      currentGroupIndex.value >= lastGroupIndex.value
    ) {
      return
    }

    autoTurnPaused.value = !autoTurnPaused.value
    if (autoTurnPaused.value) {
      pauseAutoTurnTick()
    } else {
      resetAutoTurnCountdown()
    }
  }

  watch(
    () =>
      [
        currentSettings.value.autoTurn,
        currentSettings.value.mode,
        currentSettings.value.autoTurnInterval,
      ] as const,
    () => {
      resetAutoTurnCountdown()
    },
  )

  watch(settingsOpen, (open) => {
    if (open) {
      pauseAutoTurnTick()
    } else {
      onScheduleChromeHide?.()
      resetAutoTurnCountdown()
    }
  })

  watch(documentVisibility, (state) => {
    if (state === 'hidden') {
      pauseAutoTurnTick()
    } else {
      resetAutoTurnCountdown()
    }
  })

  if (getCurrentScope()) {
    onScopeDispose(() => {
      stopAutoTurnCountdown()
    })
  }

  return {
    autoTurnRemaining,
    autoTurnPaused,
    canAutoTurnRun,
    startAutoTurnCountdown,
    stopAutoTurnCountdown,
    resetAutoTurnCountdown,
    toggleAutoTurnPause,
  }
}

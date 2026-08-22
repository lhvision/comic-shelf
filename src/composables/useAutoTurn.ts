import {
  computed,
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
  settings: MaybeRefOrGetter<ReaderSettings> | ReaderSettings
  currentGroupIndex: Ref<number>
  lastGroupIndex: ComputedRef<number>
  settingsOpen: Ref<boolean>
  onAdvance: () => void
  onScheduleChromeHide?: () => void
}

/**
 * 阅读器自动翻页状态机与定时器：
 * 负责按固定秒数倒计时、页面可见性联动、暂停/继续切换与切屏推进。
 */
export function useAutoTurn(options: UseAutoTurnOptions) {
  const { settings, lastGroupIndex, settingsOpen, onAdvance, onScheduleChromeHide } = options

  const currentSettings = computed(() => toValue(settings))
  const autoTurnRemaining = ref(currentSettings.value.autoTurnInterval)
  const autoTurnPaused = ref(false)
  const documentVisibility = useDocumentVisibility()

  function canAutoTurnRun() {
    return (
      currentSettings.value.autoTurn &&
      !autoTurnPaused.value &&
      !settingsOpen.value &&
      documentVisibility.value === 'visible' &&
      options.currentGroupIndex.value < lastGroupIndex.value
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
    if (!currentSettings.value.autoTurn || autoTurnPaused.value) return
    startAutoTurnCountdown()
  }

  function toggleAutoTurnPause() {
    if (
      !currentSettings.value.autoTurn ||
      settingsOpen.value ||
      options.currentGroupIndex.value >= lastGroupIndex.value
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
    () => currentSettings.value.autoTurn,
    (enabled) => {
      autoTurnPaused.value = false
      if (enabled) resetAutoTurnCountdown()
      else stopAutoTurnCountdown()
    },
  )

  watch(
    () => currentSettings.value.autoTurnInterval,
    () => resetAutoTurnCountdown(),
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
    if (state === 'hidden') pauseAutoTurnTick()
    else resetAutoTurnCountdown()
  })

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

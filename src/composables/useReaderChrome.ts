import { ref, watch, type Ref } from 'vue'
import { useTimeoutFn } from '@vueuse/core'

export interface UseReaderChromeOptions {
  settingsOpen: Ref<boolean>
  filmstripOpen?: Ref<boolean>
  hideDelay?: number
}

/**
 * 阅读器顶栏/HUD 延时隐藏与交互唤醒控制：
 * 负责自动排程隐藏、临时唤醒和手动显隐切换。
 */
export function useReaderChrome(options: UseReaderChromeOptions) {
  const { settingsOpen, filmstripOpen, hideDelay = 2600 } = options
  const chromeVisible = ref(true)

  const { start: startChromeHide, stop: stopChromeHide } = useTimeoutFn(
    () => {
      if (!settingsOpen.value && !filmstripOpen?.value) {
        chromeVisible.value = false
      }
    },
    hideDelay,
    { immediate: false },
  )

  if (filmstripOpen) {
    watch(filmstripOpen, (open) => {
      if (open) {
        stopChromeHide()
      } else {
        scheduleChromeHide()
      }
    })
  }

  function showChromeTemporarily() {
    chromeVisible.value = true
    stopChromeHide()
    startChromeHide()
  }

  function scheduleChromeHide() {
    stopChromeHide()
    startChromeHide()
  }

  function toggleChrome() {
    chromeVisible.value = !chromeVisible.value
    if (chromeVisible.value) {
      startChromeHide()
    } else {
      stopChromeHide()
    }
  }

  return {
    chromeVisible,
    showChromeTemporarily,
    scheduleChromeHide,
    toggleChrome,
  }
}

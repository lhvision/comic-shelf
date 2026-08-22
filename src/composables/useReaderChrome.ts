import { ref, type Ref } from 'vue'
import { useTimeoutFn } from '@vueuse/core'

export interface UseReaderChromeOptions {
  settingsOpen: Ref<boolean>
  hideDelay?: number
}

/**
 * 阅读器顶栏/HUD 延时隐藏与交互唤醒控制：
 * 负责自动排程隐藏、临时唤醒和手动显隐切换。
 */
export function useReaderChrome(options: UseReaderChromeOptions) {
  const { settingsOpen, hideDelay = 2600 } = options
  const chromeVisible = ref(true)

  const { start: startChromeHide, stop: stopChromeHide } = useTimeoutFn(
    () => {
      if (!settingsOpen.value) {
        chromeVisible.value = false
      }
    },
    hideDelay,
    { immediate: false },
  )

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
    }
  }

  return {
    chromeVisible,
    showChromeTemporarily,
    scheduleChromeHide,
    toggleChrome,
  }
}

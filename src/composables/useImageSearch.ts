import { ref, shallowRef } from 'vue'
import { createGlobalState, tryOnMounted, tryOnScopeDispose } from '@vueuse/core'
import { api } from '@/api/client'
import type { ImageSearchResultItem } from '@/types'

const MAX_AUTO_RETRIES = 3
const RETRY_INTERVAL_MS = 6000

export const useImageSearch = createGlobalState(() => {
  const isAvailable = ref(false)
  const isChecking = ref(false)
  const isSearching = ref(false)
  const error = ref('')
  const searchImageFile = shallowRef<File | null>(null)
  const searchImagePreviewUrl = ref('')
  const searchResults = shallowRef<ImageSearchResultItem[] | null>(null)
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let searchAbortController: AbortController | null = null
  let autoRetryCount = 0
  let inFlightCheck: Promise<boolean> | null = null
  let isDisposed = false
  let isManualRequested = false

  const clearRetryTimer = () => {
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
  }

  const scheduleRetry = () => {
    if (isDisposed || isManualRequested) return
    autoRetryCount++
    if (autoRetryCount < MAX_AUTO_RETRIES && typeof window !== 'undefined') {
      clearRetryTimer()
      retryTimer = setTimeout(() => {
        void checkStatus()
      }, RETRY_INTERVAL_MS)
    }
  }

  const checkStatus = async (manual = false): Promise<boolean> => {
    if (manual) {
      isManualRequested = true
      clearRetryTimer()
    }
    if (inFlightCheck) return inFlightCheck

    isChecking.value = true
    inFlightCheck = (async () => {
      try {
        const data = await api.imageSearchStatus()
        isAvailable.value = Boolean(data.available)
        if (isAvailable.value) {
          autoRetryCount = 0
          clearRetryTimer()
        } else {
          scheduleRetry()
        }
        return isAvailable.value
      } catch {
        isAvailable.value = false
        scheduleRetry()
        return false
      } finally {
        isChecking.value = false
        inFlightCheck = null
      }
    })()
    return inFlightCheck
  }

  tryOnMounted(() => {
    void checkStatus()
  })

  const clearImage = () => {
    if (searchAbortController) {
      searchAbortController.abort()
      searchAbortController = null
    }
    if (searchImagePreviewUrl.value) {
      URL.revokeObjectURL(searchImagePreviewUrl.value)
    }
    searchImagePreviewUrl.value = ''
    searchImageFile.value = null
    searchResults.value = null
    error.value = ''
  }

  tryOnScopeDispose(() => {
    isDisposed = true
    if (searchAbortController) {
      searchAbortController.abort()
      searchAbortController = null
    }
    clearRetryTimer()
    clearImage()
  })

  const searchWithFile = async (file: File) => {
    clearImage()
    const controller = new AbortController()
    searchAbortController = controller

    searchImageFile.value = file
    searchImagePreviewUrl.value = URL.createObjectURL(file)
    isSearching.value = true
    error.value = ''

    try {
      const results = await api.imageSearch(file, { signal: controller.signal })
      if (searchAbortController === controller) {
        searchResults.value = results
      }
    } catch (e: unknown) {
      if (controller.signal.aborted) return
      error.value = e instanceof Error ? e.message : '以图搜图请求失败'
      searchResults.value = null
    } finally {
      if (searchAbortController === controller) {
        isSearching.value = false
        searchAbortController = null
      }
    }
  }

  const handlePaste = (event: ClipboardEvent) => {
    if (!isAvailable.value) return
    const items = event.clipboardData?.items
    if (!items) return

    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) {
          event.preventDefault()
          void searchWithFile(file)
          return
        }
      }
    }
  }

  const handleDrop = (event: DragEvent) => {
    if (!isAvailable.value) return
    const files = event.dataTransfer?.files
    if (!files) return

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      if (file && file.type.startsWith('image/')) {
        event.preventDefault()
        void searchWithFile(file)
        return
      }
    }
  }

  const resetState = () => {
    clearRetryTimer()
    if (searchAbortController) {
      searchAbortController.abort()
      searchAbortController = null
    }
    clearImage()
    isAvailable.value = false
    isChecking.value = false
    isSearching.value = false
    autoRetryCount = 0
    inFlightCheck = null
    isDisposed = false
    isManualRequested = false
  }

  return {
    isAvailable,
    isChecking,
    isSearching,
    error,
    searchImageFile,
    searchImagePreviewUrl,
    searchResults,
    searchWithFile,
    clearImage,
    checkStatus,
    handlePaste,
    handleDrop,
    resetState,
  }
})

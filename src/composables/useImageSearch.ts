import { ref, shallowRef } from 'vue'
import { tryOnMounted, tryOnScopeDispose } from '@vueuse/core'
import { api } from '@/api/client'
import type { ImageSearchResultItem } from '@/types'

export function useImageSearch() {
  const isAvailable = ref(false)
  const isSearching = ref(false)
  const error = ref('')
  const searchImageFile = shallowRef<File | null>(null)
  const searchImagePreviewUrl = ref('')
  const searchResults = shallowRef<ImageSearchResultItem[] | null>(null)
  let retryTimer: ReturnType<typeof setTimeout> | null = null

  const checkStatus = async () => {
    try {
      const data = await api.imageSearchStatus()
      isAvailable.value = Boolean(data.available)
      if (!isAvailable.value && typeof window !== 'undefined') {
        if (retryTimer) clearTimeout(retryTimer)
        retryTimer = setTimeout(() => {
          void checkStatus()
        }, 6000)
      }
    } catch {
      isAvailable.value = false
    }
  }

  tryOnMounted(() => {
    void checkStatus()
  })

  const clearImage = () => {
    if (searchImagePreviewUrl.value) {
      URL.revokeObjectURL(searchImagePreviewUrl.value)
    }
    searchImagePreviewUrl.value = ''
    searchImageFile.value = null
    searchResults.value = null
    error.value = ''
  }

  tryOnScopeDispose(() => {
    if (retryTimer) clearTimeout(retryTimer)
    clearImage()
  })

  const searchWithFile = async (file: File) => {
    clearImage()
    searchImageFile.value = file
    searchImagePreviewUrl.value = URL.createObjectURL(file)
    isSearching.value = true
    error.value = ''

    try {
      const results = await api.imageSearch(file)
      searchResults.value = results
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '以图搜图请求失败'
      searchResults.value = null
    } finally {
      isSearching.value = false
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

  return {
    isAvailable,
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
  }
}

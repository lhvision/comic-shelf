import { ref, shallowRef } from 'vue'
import { tryOnMounted, tryOnScopeDispose } from '@vueuse/core'
import type { ImageSearchResultItem, ImageSearchStatus } from '@/types'

export function useImageSearch() {
  const isAvailable = ref(false)
  const isSearching = ref(false)
  const error = ref('')
  const searchImageFile = shallowRef<File | null>(null)
  const searchImagePreviewUrl = ref('')
  const searchResults = shallowRef<ImageSearchResultItem[] | null>(null)

  const checkStatus = async () => {
    try {
      const res = await fetch('/api/search/image/status')
      if (res.ok) {
        const data: ImageSearchStatus = await res.json()
        isAvailable.value = data.available
      } else {
        isAvailable.value = false
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
    clearImage()
  })

  const searchWithFile = async (file: File) => {
    clearImage()
    searchImageFile.value = file
    searchImagePreviewUrl.value = URL.createObjectURL(file)
    isSearching.value = true
    error.value = ''

    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('/api/search/image', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        throw new Error((await res.text()) || 'Visual search failed')
      }
      searchResults.value = await res.json()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Error occurred during image search'
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

import { ref } from 'vue'
import { tryOnScopeDispose } from '@vueuse/core'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useLibraryStore } from '@/stores/library'
import type { DiscoveryFeed, DiscoveryItem, DiscoveryTimeframe } from '@/types'

export function useDiscovery() {
  const timeframe = ref<DiscoveryTimeframe>('week')
  const feed = ref<DiscoveryFeed | null>(null)
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref<string | null>(null)
  const ingestingMap = ref<Record<string, boolean>>({})
  let activeAbortController: AbortController | null = null

  const { toast } = useToast()
  const libraryStore = useLibraryStore()

  tryOnScopeDispose(() => {
    if (activeAbortController) {
      activeAbortController.abort()
      activeAbortController = null
    }
  })

  async function loadRanking(tf: DiscoveryTimeframe = timeframe.value, refresh = false) {
    if (activeAbortController) {
      activeAbortController.abort()
    }
    const controller = new AbortController()
    activeAbortController = controller

    timeframe.value = tf
    if (refresh) {
      refreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null

    try {
      const data = await api.discoveryRanking(tf, refresh, { signal: controller.signal })
      if (activeAbortController === controller) {
        feed.value = data
      }
    } catch (err) {
      if (controller.signal.aborted) return
      const msg = err instanceof Error ? err.message : String(err)
      error.value = msg
      toast(`获取排行榜失败：${msg}`, 'error')
    } finally {
      if (activeAbortController === controller) {
        loading.value = false
        refreshing.value = false
        activeAbortController = null
      }
    }
  }

  async function ingestComic(item: DiscoveryItem) {
    if (item.in_library || ingestingMap.value[item.source_id]) {
      return
    }

    ingestingMap.value[item.source_id] = true
    try {
      await api.importComic({
        id: item.source_id,
        source: item.source,
        prefetch_covers: 4,
        prefetch_all: false,
      })
      item.in_library = true
      await libraryStore.load()
      toast(
        `已收录《${item.title.length > 16 ? item.title.slice(0, 16) + '…' : item.title}》`,
        'info',
      )
    } catch (err) {
      toast(`收录失败：${err instanceof Error ? err.message : String(err)}`, 'error')
    } finally {
      delete ingestingMap.value[item.source_id]
    }
  }

  return {
    timeframe,
    feed,
    loading,
    refreshing,
    error,
    ingestingMap,
    loadRanking,
    ingestComic,
  }
}

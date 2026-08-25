import { ref } from 'vue'
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

  const { toast } = useToast()
  const libraryStore = useLibraryStore()

  async function loadRanking(tf: DiscoveryTimeframe = timeframe.value, refresh = false) {
    timeframe.value = tf
    if (refresh) {
      refreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null

    try {
      const data = await api.discoveryRanking(tf, refresh)
      feed.value = data
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      error.value = msg
      toast(`获取排行榜失败：${msg}`, 'error')
    } finally {
      loading.value = false
      refreshing.value = false
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

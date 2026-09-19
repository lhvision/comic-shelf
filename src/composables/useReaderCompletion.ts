/**
 * @file useReaderCompletion.ts
 * @description 阅读器完读卡片、相关推荐与书架跳转编排。
 *
 * 遵循 docs/agents/frontend.md 规范：
 * - 纯领域逻辑组合式函数；
 * - 聚合完读进度保存、智能相关推荐与跨作品直达路由。
 */

import { computed, onMounted, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useLibraryStore } from '@/stores/library'
import { useAuth } from '@/composables/useAuth'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { useReaderRecommendations } from '@/composables/useReaderRecommendations'
import type { ComicDetail } from '@/types'

export interface UseReaderCompletionOptions {
  /** 漫画来源渠道 */
  source: Ref<string>
  /** 漫画车号 ID */
  sourceId: Ref<string>
  /** 漫画完整详情引用 */
  detail: Ref<ComicDetail | null>
  /** 全书/全话总页数 */
  total: Ref<number>
  /** 上次阅读进度页码 */
  lastRead: Ref<number>
}

export function useReaderCompletion(options: UseReaderCompletionOptions) {
  const { source, sourceId, detail, total, lastRead } = options
  const router = useRouter()
  const libraryStore = useLibraryStore()
  const { userId, isDirectPass } = useAuth()
  const { broadcastLocalChange } = useSystemEvents()

  onMounted(() => {
    if (libraryStore.items.length === 0 && !isDirectPass.value) {
      void libraryStore.load()
    }
  })

  const recommendTarget = computed(() => {
    if (!detail.value?.meta) return null
    return {
      source: source.value,
      source_id: sourceId.value,
      authors: detail.value.meta.authors,
      works: detail.value.meta.works,
      tags: detail.value.meta.tags,
    }
  })

  const { recommendations: rawRecommendations } = useReaderRecommendations(
    recommendTarget,
    computed(() => libraryStore.items),
    3,
  )
  const recommendations = computed(() => (isDirectPass.value ? [] : rawRecommendations.value))

  function onReaderCompleted() {
    const finalPage = detail.value?.meta.page_count ?? total.value
    if (finalPage > 0) {
      lastRead.value = finalPage
      libraryStore.setReadingProgressLocal(source.value, sourceId.value, finalPage, userId.value)
      broadcastLocalChange({
        action: 'reading_progress_changed',
        source: source.value,
        source_id: sourceId.value,
        last_page: finalPage,
        timestamp: Date.now(),
      })
    }
  }

  function onSelectComic(nextSource: string, nextSourceId: string) {
    const item = libraryStore.byId(nextSource, nextSourceId)
    const targetPage =
      item?.last_page && item.last_page > 0 && item.last_page < item.page_count ? item.last_page : 1
    void router.push(`/comic/${nextSource}/${nextSourceId}/read/${targetPage}`)
  }

  function onOpenComicDetail(nextSource: string, nextSourceId: string) {
    void router.push(`/comic/${nextSource}/${nextSourceId}`)
  }

  function onBackToShelf() {
    if (isDirectPass.value) {
      void router.push(`/comic/${source.value}/${sourceId.value}`)
    } else {
      void router.push('/')
    }
  }

  return {
    recommendations,
    onReaderCompleted,
    onSelectComic,
    onOpenComicDetail,
    onBackToShelf,
  }
}

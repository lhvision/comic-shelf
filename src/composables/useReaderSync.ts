/**
 * @file useReaderSync.ts
 * @description 阅读器进度持久化、跨标签页 SSE 广播与漫画排版首选项记忆。
 *
 * 遵循 docs/agents/frontend.md 规范：
 * - 纯领域逻辑组合式函数；
 * - 处理进度去抖同步、组件卸载回写与用户偏好联动。
 */

import { onBeforeUnmount, watch, type Ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { useAuth } from '@/composables/useAuth'
import { useLibraryStore } from '@/stores/library'
import type { ComicDetail } from '@/types'

export interface UseReaderSyncOptions {
  /** 漫画渠道标识 */
  source: Ref<string>
  /** 漫画车号 ID */
  sourceId: Ref<string>
  /** 漫画完整详情数据引用 */
  detail: Ref<ComicDetail | null>
  /** 当前阅读的页码 */
  currentPage: Ref<number>
  /** 上次阅读记录引用 */
  lastRead: Ref<number>
  /** 清理激活漫画特定配置回调 */
  clearActiveComic: () => void
  /** 应用当前漫画的排版与翻页方向偏好 */
  applyComicPreferences: (source: string, sourceId: string, tags?: string[]) => void
  /** 前后画页按需预加载回调 */
  preloadAround: (page: number) => void
}

export function useReaderSync(options: UseReaderSyncOptions) {
  const {
    source,
    sourceId,
    detail,
    currentPage,
    lastRead,
    clearActiveComic,
    applyComicPreferences,
    preloadAround,
  } = options

  const libraryStore = useLibraryStore()
  const { broadcastLocalChange } = useSystemEvents()
  const { userId } = useAuth()

  const broadcastReadingProgress = useDebounceFn((page: number) => {
    if (page > 0 && source.value && sourceId.value) {
      broadcastLocalChange({
        action: 'reading_progress_changed',
        source: source.value,
        source_id: sourceId.value,
        last_page: page,
        timestamp: Date.now(),
      })
    }
  }, 800)

  watch(currentPage, (page) => {
    lastRead.value = page
    libraryStore.setReadingProgressLocal(source.value, sourceId.value, page, userId.value)
    void broadcastReadingProgress(page)
    preloadAround(page)
  })

  watch([source, sourceId], () => {
    clearActiveComic()
  })

  watch(
    () => detail.value,
    (d) => {
      if (d && source.value && sourceId.value) {
        applyComicPreferences(source.value, sourceId.value, d.meta.tags)
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    clearActiveComic()
    lastRead.value = currentPage.value
    if (currentPage.value > 0 && source.value && sourceId.value) {
      broadcastLocalChange({
        action: 'reading_progress_changed',
        source: source.value,
        source_id: sourceId.value,
        last_page: currentPage.value,
        timestamp: Date.now(),
      })
    }
  })
}

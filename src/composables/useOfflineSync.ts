/**
 * @file useOfflineSync.ts
 * @description 客户端网络状态感知与离线事务自愈回写管道。
 *
 * 核心契约：
 * 1. 基于 VueUse useNetwork 感知浏览器在线/离线状态；
 * 2. 在网络重获连接（offline -> online）或页面前台唤醒时，静默消费 offline_actions 队列；
 * 3. 将离线产生的阅读进度与喜欢变动回写至后端 SQLite；
 * 4. 同步完成后静默触发 Pinia 书架 Store SWR 对齐最新元数据；
 * 5. 采用单例 Global State，保证全应用生命周期统一调度。
 */

import { ref, watch } from 'vue'
import { createGlobalState, useNetwork } from '@vueuse/core'
import { api } from '@/api/client'
import {
  enqueueOfflineAction,
  getOfflineActions,
  removeOfflineAction,
  type OfflineActionType,
} from '@/utils/offlineDb'
import { useLibraryStore } from '@/stores/library'
import { useAuth } from '@/composables/useAuth'

export const useOfflineSync = createGlobalState(() => {
  const { isOnline } = useNetwork()
  const { userId } = useAuth()
  const isSyncing = ref(false)
  const lastSyncTime = ref<number | null>(null)

  /**
   * 记录离线操作事务至 IndexedDB 队列
   */
  async function recordOfflineAction(
    type: OfflineActionType,
    payload: Record<string, unknown>,
  ): Promise<void> {
    await enqueueOfflineAction({
      type,
      payload,
      userId: userId.value || 'default',
    })
    if (isOnline.value) {
      void flushPendingActions()
    }
  }

  /**
   * 静默消费回写所有待处理的离线操作
   */
  async function flushPendingActions(): Promise<void> {
    if (isSyncing.value || !isOnline.value) return
    isSyncing.value = true

    try {
      const actions = await getOfflineActions()
      if (actions.length === 0) {
        lastSyncTime.value = Date.now()
        return
      }

      const currentUid = userId.value || 'default'

      for (const item of actions) {
        if (!isOnline.value) break
        // 安全护栏：如果记录归属与当前登录用户不匹配，暂不跨身份提交，防止权限越权与进度污染
        if (item.userId && item.userId !== currentUid) {
          continue
        }
        try {
          if (item.type === 'reading_progress') {
            const { source, sourceId, page, total_pages } = item.payload as {
              source: string
              sourceId: string
              page: number
              total_pages?: number
            }
            if (source && sourceId && typeof page === 'number') {
              await api.saveReadingProgress(source, sourceId, page, total_pages)
            }
          } else if (item.type === 'favorite') {
            const { source, sourceId, favorite } = item.payload as {
              source: string
              sourceId: string
              favorite: boolean
            }
            if (source && sourceId && typeof favorite === 'boolean') {
              await api.setFavorite(source, sourceId, favorite)
            }
          }
          await removeOfflineAction(item.id)
        } catch {
          // 单个操作因网络中断失败则中断本轮消费，留待下一轮重试
          break
        }
      }

      lastSyncTime.value = Date.now()
    } finally {
      isSyncing.value = false
    }
  }

  // 监听网络连接自愈：网络由离线变为在线时自动回写并静默刷新书架
  watch(isOnline, (online, wasOnline) => {
    if (online && wasOnline === false) {
      void (async () => {
        await flushPendingActions()
        const libraryStore = useLibraryStore()
        await libraryStore.load(true)
      })()
    }
  })

  return {
    isOnline,
    isSyncing,
    lastSyncTime,
    recordOfflineAction,
    flushPendingActions,
  }
})

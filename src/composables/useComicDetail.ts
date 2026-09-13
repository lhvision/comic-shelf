/**
 * @file useComicDetail.ts
 * @description 漫画详情生命周期、SWR 内存态占位、离线容错与后台任务对齐 Composable。
 *
 * 领域契约（CONTEXT.md）：
 * 1. 详情元数据内存态热复用（Detail In-memory SWR Cache）：
 *    优先命中 Pinia Store 内存中的完整详情或概要占位（createPlaceholderDetail），
 *    消除跨路由跳转的白屏/骨架屏二次闪烁与重复 JSON 反序列化；
 * 2. 严格任务驱动轮询（Job-driven Polling / ADR 0010）：
 *    仅在后台明确存在活跃下载任务（job.running === true）时对齐任务状态；
 * 3. 离线容错与降级自愈：
 *    网络断开或请求失败时，兜底从本地 IndexedDB 还原完整作品结构；
 * 4. 系统事件响应：
 *    侦听全局 SSE 与跨标签页广播，原地同步收藏与数据变动，避免不必要的大 JSON 重拉。
 */

import { onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { api } from '@/api/client'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { useLibraryStore, createPlaceholderDetail } from '@/stores/library'
import type { CacheJob, ComicDetail } from '@/types'

/**
 * useComicDetail 入参依赖配置
 */
export interface UseComicDetailOptions {
  /** 漫画来源渠道（如 'jm', 'picacg', 'local'） */
  source: Ref<string>
  /** 作品唯一车号/标识 */
  sourceId: Ref<string>
  /** 远程数据拉取成功后的回调（例如预热图片或章节切片） */
  onLoaded?: (detail: ComicDetail) => void
  /** 命中本地 IndexedDB 离线降级时的回调 */
  onFallback?: (fallback: ComicDetail) => void
  /** 缓存任务状态对齐回调 */
  onSyncJobState?: (job: CacheJob) => void
  /** 加载彻底失败后的异常回调 */
  onError?: (error: unknown) => void
}

/**
 * useComicDetail 返回契约
 */
export interface UseComicDetailReturn {
  /** 响应式漫画详情实体 */
  detail: Ref<ComicDetail | null>
  /** 是否处于初次加载/刷新中 */
  loading: Ref<boolean>
  /** 手动触发详情加载（支持静默与绕过缓存） */
  load: (silent?: boolean, bypassCache?: boolean) => Promise<void>
}

/**
 * 漫画详情聚合管理 Hook
 * @param options 依赖选项
 * @returns 详情实体与生命周期控制接口
 */
export function useComicDetail(options: UseComicDetailOptions): UseComicDetailReturn {
  const { source, sourceId, onLoaded, onFallback, onSyncJobState, onError } = options

  const store = useLibraryStore()
  const { userId } = useAuth()
  const { toast } = useToast()
  const { lastLibraryEvent } = useSystemEvents()

  // SWR 即时占位：若书架 Store 中已有完整缓存或概要，立即构造初态渲染
  const cachedSummary = store.byId(source.value, sourceId.value)
  const existingDetail = store.getDetail(source.value, sourceId.value)
  const detail = ref<ComicDetail | null>(
    existingDetail ?? (cachedSummary ? createPlaceholderDetail(cachedSummary) : null),
  )
  const loading = ref(!detail.value)
  let loadAbortController: AbortController | null = null

  /**
   * 执行远端或本地详情拉取
   * @param silent 是否静默刷新（不闪现骨架屏）
   * @param bypassCache 是否强制绕过客户端内存缓存重查后端
   */
  async function load(silent = false, bypassCache = false): Promise<void> {
    if (loadAbortController) {
      loadAbortController.abort()
    }
    const controller = new AbortController()
    loadAbortController = controller

    if (!silent && !detail.value) {
      loading.value = true
    }

    try {
      const data = await api.detail(source.value, sourceId.value, {
        signal: controller.signal,
        bypassCache,
      })
      if (controller.signal.aborted) return

      detail.value = data
      store.setDetail(data, userId.value)
      onLoaded?.(data)

      // 严格任务驱动轮询：同步后台活跃缓存任务
      try {
        const job = await api.cacheJob(source.value, sourceId.value, { signal: controller.signal })
        if (!controller.signal.aborted && onSyncJobState) {
          onSyncJobState(job)
        }
      } catch {
        // 轮询任务探测静默容错
      }
    } catch (err) {
      if (controller.signal.aborted) return

      // 离线容错降级：优先命中本地 IndexedDB 或书架概要占位
      const offlineDetail = await store.getOrFetchOfflineDetail(
        source.value,
        sourceId.value,
        userId.value,
      )
      const summary = store.byId(source.value, sourceId.value)
      const fallback = offlineDetail || (summary ? createPlaceholderDetail(summary) : null)

      if (fallback) {
        detail.value = fallback
        onFallback?.(fallback)
        return
      }

      if (onError) {
        onError(err)
      } else {
        toast(err instanceof Error ? err.message : String(err), 'error')
      }
    } finally {
      if (loadAbortController === controller) {
        if (!silent) loading.value = false
        loadAbortController = null
      }
    }
  }

  // 跨漫画切换时重新挂载 SWR 占位并重新拉取
  watch(
    () => [source.value, sourceId.value],
    () => {
      const summary = store.byId(source.value, sourceId.value)
      const existing = store.getDetail(source.value, sourceId.value)
      detail.value = existing ?? (summary ? createPlaceholderDetail(summary) : null)
      loading.value = !detail.value
      void load()
    },
  )

  // 侦听全局系统事件
  watch(lastLibraryEvent, (event) => {
    if (!event) return
    if (
      (!event.source || event.source === source.value) &&
      (!event.source_id || event.source_id === sourceId.value)
    ) {
      // 收藏轻量状态变动由各模块就地消化
      if (event.action === 'favorite_changed') {
        if (detail.value?.meta && typeof event.favorite === 'boolean') {
          detail.value.meta.favorite = event.favorite
        }
        return
      }
      if (event.action === 'reading_progress_changed') {
        return
      }
      void load(true, true)
    }
  })

  onBeforeUnmount(() => {
    if (loadAbortController) {
      loadAbortController.abort()
      loadAbortController = null
    }
  })

  return {
    detail,
    loading,
    load,
  }
}

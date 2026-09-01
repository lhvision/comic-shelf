/**
 * @file useReaderData.ts
 * @description 阅读器数据加载、生命周期竞态隔离与路由状态同步组合式函数。
 *
 * 核心职责：
 * 1. 漫画详情数据拉取（`api.detail`）与 `AbortController` 竞态取消；
 * 2. 路由参数解析（`source`, `sourceId`, `scopeId`）与 404/网络异常 Toast 容错拦截；
 * 3. 漫画车号变更防御性响应（`[source, sourceId]` 监听重新拉取）；
 * 4. 阅读历史页码（`lastRead`）响应式同步；
 * 5. 详情页/子路由返回路径（`backTarget` / `backToDetail`）计算与导航。
 */

import { computed, onBeforeUnmount, onMounted, ref, watch, type ComputedRef, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useLastRead } from '@/composables/useLastRead'
import { useIllustrationPool } from '@/composables/useIllustrationPool'
import type { ComicDetail } from '@/types'

/**
 * `useReaderData` 初始化依赖项契约
 */
export interface UseReaderDataOptions {
  /** 详情数据成功加载并就绪时的回调函数 */
  onLoaded?: (detail: ComicDetail) => void | Promise<void>
}

/**
 * `useReaderData` 返回值契约
 */
export interface UseReaderDataReturn {
  /** 漫画元数据详情（加载中为 null） */
  detail: Ref<ComicDetail | null>
  /** 全局初次加载状态指示 */
  loading: Ref<boolean>
  /** 随机看板插画变体序号或路径 */
  loadingVariant: Ref<string>
  /** 漫画数据源 Provider 名称（如 'jm' / 'local'） */
  source: ComputedRef<string>
  /** 漫画唯一 ID */
  sourceId: ComputedRef<string>
  /** 当前锁定的章节 ID（无则为整本全局） */
  scopeId: Ref<string | null>
  /** 返回详情页/子路由的目标 URL */
  backTarget: ComputedRef<string>
  /** 返回详情页/子路由的方法 */
  backToDetail: () => void
  /** 继续阅读持久化页码 Ref */
  lastRead: Ref<number>
  /** 手动重新加载当前漫画数据 */
  loadDetail: () => Promise<void>
}

/**
 * 阅读器数据流与路由状态同步 Hook
 * @param options 配置依赖
 * @returns 阅读器数据与路由导航状态
 */
export function useReaderData(options: UseReaderDataOptions = {}): UseReaderDataReturn {
  const { onLoaded } = options

  const route = useRoute()
  const router = useRouter()
  const { toast } = useToast()

  const source = computed(() => String(route.params.source ?? ''))
  const sourceId = computed(() => String(route.params.sourceId ?? ''))
  const lastRead = useLastRead(source, sourceId)

  const detail = ref<ComicDetail | null>(null)
  const loading = ref(true)

  const { getRandomIllustration } = useIllustrationPool()
  const loadingVariant = ref(getRandomIllustration())

  /* ---------------- 章节作用域 ---------------- */
  const scopeId = ref<string | null>(null)

  watch(
    () => route.query.chapter,
    (q) => {
      scopeId.value = typeof q === 'string' && q ? q : null
    },
    { immediate: true },
  )

  const backTarget = computed(() => {
    const chapter = route.query.chapter
    if (chapter && typeof chapter === 'string') {
      return `/comic/${source.value}/${sourceId.value}/chapter/${encodeURIComponent(chapter)}`
    }
    return `/comic/${source.value}/${sourceId.value}`
  })

  function backToDetail() {
    void router.push(backTarget.value)
  }

  /* ---------------- 数据加载与生命周期 ---------------- */
  let readerAbortController: AbortController | null = null

  async function loadDetail() {
    if (!source.value || !sourceId.value) return

    if (readerAbortController) {
      readerAbortController.abort()
    }
    const controller = new AbortController()
    readerAbortController = controller
    loading.value = true

    try {
      const data = await api.detail(source.value, sourceId.value, { signal: controller.signal })
      if (controller.signal.aborted) return
      detail.value = data
      if (onLoaded) {
        await onLoaded(data)
      }
      loading.value = false
    } catch (e) {
      if (controller.signal.aborted) return
      loading.value = false
      toast(e instanceof Error ? e.message : String(e), 'error')
      void router.replace(`/comic/${source.value}/${sourceId.value}`)
    } finally {
      if (readerAbortController === controller) {
        readerAbortController = null
      }
    }
  }

  onMounted(() => {
    void loadDetail()
  })

  // 防御性监听：若在同路由组件复用状态下切换了漫画源或漫画 ID，主动拉取新详情
  watch(
    () => `${source.value}/${sourceId.value}`,
    (newKey, oldKey) => {
      if (newKey && oldKey && newKey !== oldKey) {
        void loadDetail()
      }
    },
  )

  onBeforeUnmount(() => {
    if (readerAbortController) {
      readerAbortController.abort()
      readerAbortController = null
    }
  })

  return {
    detail,
    loading,
    loadingVariant,
    source,
    sourceId,
    scopeId,
    backTarget,
    backToDetail,
    lastRead,
    loadDetail,
  }
}

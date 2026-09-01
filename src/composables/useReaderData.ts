/**
 * @file useReaderData.ts
 * @description 阅读器数据加载、生命周期竞态隔离与路由状态同步组合式函数。
 *
 * 核心职责：
 * 1. 漫画详情数据拉取（`api.detail`）与 `AbortController` 竞态取消；
 * 2. 路由参数解析（`source`, `sourceId`, `scopeId`）与 404/网络异常 Toast 容错拦截；
 * 3. 阅读历史页码（`lastRead`）与相邻画页预加载（`preloadAround`）响应式同步；
 * 4. 路由切页（`route.params.page`）与章节切换（`route.query.chapter`）动态重定位与状态重置；
 * 5. 详情页/子路由返回路径（`backTarget` / `backToDetail`）计算与导航。
 */

import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useLastRead } from '@/composables/useLastRead'
import { useIllustrationPool } from '@/composables/useIllustrationPool'
import type { ReaderSettings } from '@/composables/useReaderSettings'
import type { ComicDetail } from '@/types'

/**
 * `useReaderData` 初始化依赖项契约
 */
export interface UseReaderDataOptions {
  /** 阅读器设置（排版模式、翻页方向、单屏页数等） */
  settings: ReaderSettings
  /** 当前展示的全局/本地页码 Ref */
  currentPage: Ref<number>
  /** 当前展示的分屏分组索引 Ref（0-based） */
  currentGroupIndex: Ref<number>
  /** 当前作用域下的所有全局页码列表 */
  scopedPages: ComputedRef<number[]>
  /** 限制页码在当前章节范围内的钳制函数 */
  clampToScope: (page: number) => number
  /** 给定页码查询对应分组索引的计算函数 */
  groupIndexForPage: (page: number) => number
  /** 将滚动容器物理定位到指定分屏分组 */
  scrollToGroup: (groupIndex: number, behavior?: ScrollBehavior) => void
  /** 导航跳转到指定全局页码 */
  goToPage: (page: number, behavior?: ScrollBehavior) => void
  /** 预加载目标页码周边的图片资源 */
  preloadAround: (page: number) => void
  /** 临时唤醒阅读器悬浮顶栏与 HUD */
  showChromeTemporarily: () => void
  /** 安排延时隐藏顶栏与 HUD */
  scheduleChromeHide: () => void
  /** 重置自动翻页倒计时节拍器 */
  resetAutoTurnCountdown: () => void
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
}

/**
 * 阅读器数据流与路由状态同步 Hook
 * @param options 配置依赖
 * @returns 阅读器数据与路由导航状态
 */
export function useReaderData(options: UseReaderDataOptions): UseReaderDataReturn {
  const {
    settings,
    currentPage,
    currentGroupIndex,
    scopedPages,
    clampToScope,
    groupIndexForPage,
    scrollToGroup,
    goToPage,
    preloadAround,
    showChromeTemporarily,
    scheduleChromeHide,
    resetAutoTurnCountdown,
  } = options

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

  onMounted(async () => {
    if (readerAbortController) {
      readerAbortController.abort()
    }
    const controller = new AbortController()
    readerAbortController = controller

    try {
      const data = await api.detail(source.value, sourceId.value, { signal: controller.signal })
      if (controller.signal.aborted) return
      detail.value = data
      const initial = Number(route.params.page ?? 1)
      currentPage.value = clampToScope(initial)
      currentGroupIndex.value = groupIndexForPage(currentPage.value)
      loading.value = false

      await nextTick()
      scrollToGroup(currentGroupIndex.value, 'instant')
      scheduleChromeHide()
      preloadAround(currentPage.value)
      resetAutoTurnCountdown()
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
  })

  onBeforeUnmount(() => {
    if (readerAbortController) {
      readerAbortController.abort()
      readerAbortController = null
    }
    lastRead.value = currentPage.value
  })

  /* ---------------- 状态与路由响应式监听 ---------------- */
  watch(currentPage, (page) => {
    lastRead.value = page
    preloadAround(page)
  })

  watch(
    () => route.params.page,
    (value) => {
      const page = Number(value ?? 1)
      const pages = scopedPages.value
      if (!Number.isFinite(page) || pages.length === 0) return
      if (page < pages[0]! || page > pages[pages.length - 1]!) return
      if (page === currentPage.value) return
      goToPage(page, 'smooth')
    },
  )

  watch(
    () => `${settings.mode}|${settings.pagesPerView}|${settings.direction}`,
    async () => {
      currentGroupIndex.value = groupIndexForPage(currentPage.value)
      await nextTick()
      scrollToGroup(currentGroupIndex.value, 'instant')
      showChromeTemporarily()
      resetAutoTurnCountdown()
    },
  )

  watch(
    () => scopeId.value,
    async () => {
      if (!detail.value) return
      const clamped = clampToScope(currentPage.value)
      if (clamped !== currentPage.value) currentPage.value = clamped
      currentGroupIndex.value = groupIndexForPage(currentPage.value)
      await nextTick()
      scrollToGroup(currentGroupIndex.value, 'instant')
      showChromeTemporarily()
      resetAutoTurnCountdown()
    },
  )

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
  }
}

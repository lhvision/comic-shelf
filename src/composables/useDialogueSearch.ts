/**
 * @file useDialogueSearch.ts
 * @description 前台漫画分镜台词全文检索 Composable（基于 SQLite FTS5）。
 *
 * 核心职责：
 * 1. 提供防抖台词搜索（支持简繁互通），维护加载状态、结果集与错误状态；
 * 2. 具备严密的在途请求竞态取消（AbortController）与作用域自愈回收机制；
 * 3. 维护浮层显示状态（isOpen）与键盘焦点导航（focusedIndex）；
 * 4. 封装直达阅读器路由跳转逻辑，无缝携带 bubble_box 归一化矩形与对白文本。
 */

import { computed, ref, shallowRef, watch, type Ref, type ComputedRef } from 'vue'
import { useDebounceFn, tryOnScopeDispose } from '@vueuse/core'
import type { Router } from 'vue-router'
import { api } from '@/api/client'
import type { DialogueSearchItem } from '@/types'

export interface UseDialogueSearchOptions {
  /** 可选的漫画来源过滤（如 'jm' | 'picacg' | 'local'），不传或为空时全库检索 */
  source?: Ref<string | undefined> | ComputedRef<string | undefined>
  /** 防抖延迟时间（毫秒，默认 300ms） */
  debounceMs?: number
  /** 单次检索结果上限（默认 20 条） */
  limit?: number
}

export interface UseDialogueSearchReturn {
  /** 搜索关键词 */
  query: Ref<string>
  /** 命中的台词搜索结果列表 */
  results: Ref<DialogueSearchItem[]>
  /** 命中总条数 */
  total: Ref<number>
  /** 是否正在后台检索 */
  isSearching: Ref<boolean>
  /** 检索错误提示（无错为空字符串） */
  error: Ref<string>
  /** 下拉浮层是否展开显示 */
  isOpen: Ref<boolean>
  /** 当前键盘高亮选中的条目索引（-1 表示未选中） */
  focusedIndex: Ref<number>
  /** 是否具有有效结果 */
  hasResults: ComputedRef<boolean>
  /** 手动执行台词检索（通常供即时回车或关键词联动调用） */
  executeSearch: (immediateQuery?: string) => Promise<void>
  /** 打开下拉面板（若存在关键词） */
  open: () => void
  /** 关闭下拉面板 */
  close: () => void
  /** 清空搜索与结果并中止在途请求 */
  clear: () => void
  /** 键盘向下导航高亮项 */
  navigateNext: () => void
  /** 键盘向上导航高亮项 */
  navigatePrev: () => void
  /** 路由直达目标分镜画页并携带朱砂金墨气泡参数 */
  navigateToResult: (item: DialogueSearchItem, router: Router) => void
}

/**
 * 漫画台词检索 Composable
 */
export function useDialogueSearch(options: UseDialogueSearchOptions = {}): UseDialogueSearchReturn {
  const { source, debounceMs = 300, limit = 20 } = options

  const query = ref('')
  const results = shallowRef<DialogueSearchItem[]>([])
  const total = ref(0)
  const isSearching = ref(false)
  const error = ref('')
  const isOpen = ref(false)
  const focusedIndex = ref(-1)

  let abortController: AbortController | null = null

  const hasResults = computed(() => results.value.length > 0)

  /**
   * 中止当前在途请求并重置控制器
   */
  const abortCurrentRequest = () => {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
  }

  /**
   * 执行后端检索核心逻辑
   */
  const executeSearch = async (overrideQuery?: string) => {
    const rawQ = overrideQuery !== undefined ? overrideQuery : query.value
    const trimmed = rawQ.trim()

    // 关键词少于 2 个有效字符时重置（短词全表扫描防爆守卫）
    if (trimmed.length < 2) {
      abortCurrentRequest()
      results.value = []
      total.value = 0
      isSearching.value = false
      error.value = ''
      if (!trimmed) {
        isOpen.value = false
      }
      focusedIndex.value = -1
      return
    }

    abortCurrentRequest()
    const controller = new AbortController()
    abortController = controller

    isSearching.value = true
    error.value = ''
    focusedIndex.value = -1

    try {
      const srcVal = source?.value || undefined
      const response = await api.searchDialogue(trimmed, srcVal, limit, {
        signal: controller.signal,
      })

      // 若未被后续请求中止，更新视图状态
      if (!controller.signal.aborted) {
        results.value = response.results ?? []
        total.value = response.total ?? results.value.length
        // 关键整改：仅当检索命中有效台词，或用户已显式打开面板时才展示；
        // 自动检索 0 条时保持静默，绝不破坏性弹窗遮挡书架正常书名搜索
        if (results.value.length > 0 || isOpen.value) {
          isOpen.value = true
        }
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return
      results.value = []
      total.value = 0
      const msg = err instanceof Error ? err.message : String(err)
      error.value = msg || '检索分镜台词失败，请稍后重试'
    } finally {
      if (!controller.signal.aborted) {
        isSearching.value = false
      }
    }
  }

  /**
   * 防抖触发检索
   */
  const debouncedSearch = useDebounceFn(() => {
    void executeSearch()
  }, debounceMs)

  /**
   * 监听 query 变更，自动触发防抖检索
   */
  watch(query, (newVal) => {
    if (!newVal.trim()) {
      abortCurrentRequest()
      results.value = []
      total.value = 0
      isSearching.value = false
      error.value = ''
      isOpen.value = false
      focusedIndex.value = -1
      return
    }
    void debouncedSearch()
  })

  /**
   * 监听 source 切换，清空旧缓存，若面板开启则刷新
   */
  if (source) {
    watch(source, () => {
      results.value = []
      total.value = 0
      focusedIndex.value = -1
      if (query.value.trim() && isOpen.value) {
        void executeSearch()
      }
    })
  }

  const open = () => {
    if (query.value.trim()) {
      isOpen.value = true
      if (results.value.length === 0 && !isSearching.value && query.value.trim().length >= 2) {
        void executeSearch()
      }
    }
  }

  const close = () => {
    isOpen.value = false
    focusedIndex.value = -1
  }

  const clear = () => {
    abortCurrentRequest()
    query.value = ''
    results.value = []
    total.value = 0
    isSearching.value = false
    error.value = ''
    isOpen.value = false
    focusedIndex.value = -1
  }

  const navigateNext = () => {
    if (!hasResults.value) return
    if (focusedIndex.value < results.value.length - 1) {
      focusedIndex.value++
    } else {
      focusedIndex.value = 0
    }
  }

  const navigatePrev = () => {
    if (!hasResults.value) return
    if (focusedIndex.value > 0) {
      focusedIndex.value--
    } else {
      focusedIndex.value = results.value.length - 1
    }
  }

  /**
   * 导航至目标分镜画页
   */
  const navigateToResult = (item: DialogueSearchItem, router: Router) => {
    close()
    const boxParam =
      Array.isArray(item.box) && item.box.length === 4
        ? item.box.map((v) => Number(v).toFixed(4)).join(',')
        : undefined

    const queryObj: Record<string, string> = {}
    if (boxParam) queryObj.bubble_box = boxParam
    if (item.text) queryObj.bubble_text = item.text

    void router.push({
      path: `/comic/${encodeURIComponent(item.source)}/${encodeURIComponent(item.source_id)}/read/${item.page_index}`,
      query: queryObj,
    })
  }

  tryOnScopeDispose(() => {
    abortCurrentRequest()
  })

  return {
    query,
    results,
    total,
    isSearching,
    error,
    isOpen,
    focusedIndex,
    hasResults,
    executeSearch,
    open,
    close,
    clear,
    navigateNext,
    navigatePrev,
    navigateToResult,
  }
}

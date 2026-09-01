/**
 * @file useReaderNavigation.ts
 * @description 阅读器多屏滚动定位、进度计算与跨章节导航组合式函数。
 *
 * 核心职责：
 * 1. 物理视口滚动（`scrollToGroup`）：支持横向与竖向、smooth/instant 平滑过渡；
 * 2. 交互式切页跳转（`goToGroup` / `goToPage` / `prevGroup` / `nextGroup`）；
 * 3. 滚动进度换算（`onScroll`）：支持 LTR 与 RTL 反向进度，以及最邻近 Spread 自动吸附探测；
 * 4. 横向滚轮转换（`onWheel`）：将纵向滚轮差量映射为横向滚动；
 * 5. 前后环视预热（`preloadAround`）：在后台预加载当前页邻近的前后屏图片；
 * 6. 跨章节边界切入（`goNextChapter` / `goPrevChapter`）：自动维护 `?chapter=` 作用域与 URL 替换。
 */

import { getCurrentScope, onScopeDispose, ref, type ComputedRef, type Ref } from 'vue'
import type { Router } from 'vue-router'
import { pageFileUrl } from '@/api/client'
import type { Chapter } from '@/types'
import type { ReaderSettings } from '@/composables/useReaderSettings'

/**
 * `useReaderNavigation` 初始化依赖项
 */
export interface UseReaderNavigationOptions {
  /** 阅读器主体滚动容器 DOM Ref */
  scrollEl: Ref<HTMLElement | null>
  /** 阅读器设置（排版模式、翻页方向等） */
  settings: ReaderSettings
  /** 当前展示的全局/本地页码 Ref */
  currentPage: Ref<number>
  /** 当前展示的分屏分组索引 Ref（0-based） */
  currentGroupIndex: Ref<number>
  /** 分屏页码分组列表（如 [[1,2], [3,4]]） */
  pageGroups: ComputedRef<number[][]>
  /** 最后一组分屏索引 */
  lastGroupIndex: ComputedRef<number>
  /** 限制页码在当前章节范围内的钳制函数 */
  clampToScope: (page: number) => number
  /** 给定页码查询对应分组索引的计算函数 */
  groupIndexForPage: (page: number) => number
  /** 给定分组索引查询首页页码的计算函数 */
  groupFirstPage: (groupIndex: number) => number
  /** 唤醒阅读器悬浮顶栏与 HUD 的回调 */
  showChromeTemporarily: () => void
  /** 重置自动翻页倒计时的回调 */
  resetAutoTurnCountdown: () => void
  /** 漫画数据源 Provider 名称（如 'jm' / 'local'） */
  source: ComputedRef<string>
  /** 漫画唯一 ID */
  sourceId: ComputedRef<string>
  /** 下一话元数据（无下一话则为 null） */
  nextChapter: ComputedRef<Chapter | null>
  /** 上一话元数据（无上一话则为 null） */
  prevChapter: ComputedRef<Chapter | null>
  /** 当前锁定的章节 ID（无则为整本全局） */
  scopeId: Ref<string | null>
  /** 路由实例 */
  router: Router
}

/**
 * 阅读器导航与视口定位 Hook
 * @param options 配置依赖
 */
export function useReaderNavigation(options: UseReaderNavigationOptions) {
  const {
    scrollEl,
    settings,
    currentPage,
    currentGroupIndex,
    pageGroups,
    lastGroupIndex,
    clampToScope,
    groupIndexForPage,
    groupFirstPage,
    showChromeTemporarily,
    resetAutoTurnCountdown,
    source,
    sourceId,
    nextChapter,
    prevChapter,
    scopeId,
    router,
  } = options

  /** 归一化滚动进度（0.0 ~ 1.0），在 RTL 模式下自动取反以贴合阅读习惯 */
  const progressValue = ref(0)

  /**
   * 将阅读器滚动视口物理定位到指定的分屏容器
   * @param groupIndex 目标分屏索引
   * @param behavior 滚动动画行为（'smooth' | 'auto' | 'instant'）
   */
  function scrollToGroup(groupIndex: number, behavior: ScrollBehavior = 'smooth') {
    const el = scrollEl.value
    if (!el) return
    const target = el.querySelector<HTMLElement>(`[data-group-index="${groupIndex}"]`)
    if (!target) return

    if (settings.mode === 'horizontal') {
      el.scrollTo({ left: target.offsetLeft, top: 0, behavior })
    } else {
      el.scrollTo({ left: 0, top: target.offsetTop, behavior })
    }
  }

  /**
   * 业务级翻到指定分组（更新响应式状态 + 触发物理滚动 + 重置计时器）
   * @param groupIndex 目标分屏索引
   * @param behavior 滚动行为
   */
  function goToGroup(groupIndex: number, behavior: ScrollBehavior = 'smooth') {
    const clamped = Math.min(Math.max(groupIndex, 0), Math.max(0, lastGroupIndex.value))
    currentGroupIndex.value = clamped
    currentPage.value = groupFirstPage(clamped)
    scrollToGroup(clamped, behavior)
    showChromeTemporarily()
    resetAutoTurnCountdown()
  }

  /**
   * 业务级翻到指定页码（钳制作用域 + 查找对应分组 + 滚动）
   * @param page 目标全局页码
   * @param behavior 滚动行为
   */
  function goToPage(page: number, behavior: ScrollBehavior = 'smooth') {
    const clampedPage = clampToScope(page)
    const groupIndex = groupIndexForPage(clampedPage)
    currentPage.value = clampedPage
    currentGroupIndex.value = groupIndex
    scrollToGroup(groupIndex, behavior)
    showChromeTemporarily()
    resetAutoTurnCountdown()
  }

  /** 翻到上一屏 */
  function prevGroup() {
    goToGroup(currentGroupIndex.value - 1)
  }

  /** 翻到下一屏 */
  function nextGroup() {
    goToGroup(currentGroupIndex.value + 1)
  }

  let scrollRafId: number | null = null

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (scrollRafId !== null) {
        cancelAnimationFrame(scrollRafId)
        scrollRafId = null
      }
    })
  }

  /** 监听容器滚动事件（rAF 节流计算进度、探测最临近屏以更新当前页码） */
  function onScroll() {
    if (scrollRafId !== null) return
    scrollRafId = requestAnimationFrame(() => {
      scrollRafId = null
      handleScroll()
    })
  }

  function handleScroll() {
    const el = scrollEl.value
    if (!el) return

    const horizontal = settings.mode === 'horizontal'
    const rtl = horizontal && settings.direction === 'rtl'
    const position = horizontal ? el.scrollLeft : el.scrollTop
    const max = horizontal ? el.scrollWidth - el.clientWidth : el.scrollHeight - el.clientHeight
    const rawProgress = max <= 0 ? 1 : Math.min(1, Math.max(0, position / max))
    progressValue.value = rtl ? 1 - rawProgress : rawProgress

    const spreads = [...el.querySelectorAll<HTMLElement>('[data-group-index]')]
    let nearest = currentGroupIndex.value
    let bestDistance = Number.POSITIVE_INFINITY
    for (const spread of spreads) {
      const spreadPosition = horizontal ? spread.offsetLeft : spread.offsetTop
      const distance = Math.abs(spreadPosition - position)
      if (distance < bestDistance) {
        bestDistance = distance
        nearest = Number(spread.dataset.groupIndex)
      }
    }

    if (Number.isFinite(nearest) && nearest !== currentGroupIndex.value) {
      currentGroupIndex.value = nearest
      currentPage.value = groupFirstPage(nearest)
    }

    if (!settings.autoTurn && settings.mode !== 'vertical-continuous') {
      showChromeTemporarily()
    }
    resetAutoTurnCountdown()
  }

  /** 在横向翻页排版下拦截纵向滚轮并转换为横向平滑滚动 */
  function onWheel(event: WheelEvent) {
    if (settings.mode !== 'horizontal') return
    const el = scrollEl.value
    if (!el) return

    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return

    event.preventDefault()
    const windowHeight = typeof window !== 'undefined' ? window.innerHeight : 600
    const factor = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? windowHeight : 1
    el.scrollBy({ left: event.deltaY * factor, behavior: 'auto' })
    if (!settings.autoTurn) showChromeTemporarily()
    resetAutoTurnCountdown()
  }

  /** 预加载当前页前后相邻分组的图片资源到浏览器磁盘/内存缓存 */
  function preloadAround(page: number) {
    const groupIndex = groupIndexForPage(page)
    const startGroup = Math.max(0, groupIndex - 1)
    const endGroup = Math.min(pageGroups.value.length - 1, groupIndex + 1)
    for (let group = startGroup; group <= endGroup; group += 1) {
      for (const targetPage of pageGroups.value[group] ?? []) {
        const image = new Image()
        image.src = pageFileUrl(source.value, sourceId.value, targetPage)
      }
    }
  }

  /** 切换章节作用域并替换当前路由 URL 查询参数 */
  function setScope(id: string, page: number) {
    scopeId.value = id
    const target = `/comic/${source.value}/${sourceId.value}/read/${page}?chapter=${encodeURIComponent(id)}`
    void router.replace(target)
  }

  /** 跳转至下一话首页 */
  function goNextChapter() {
    const c = nextChapter.value
    if (!c) return
    setScope(c.id, c.start)
    goToPage(c.start, 'smooth')
  }

  /** 跳转至上一话末页 */
  function goPrevChapter() {
    const c = prevChapter.value
    if (!c) return
    setScope(c.id, c.start + c.page_count - 1)
    goToPage(c.start + c.page_count - 1, 'smooth')
  }

  return {
    progressValue,
    scrollToGroup,
    goToGroup,
    goToPage,
    prevGroup,
    nextGroup,
    onScroll,
    onWheel,
    preloadAround,
    setScope,
    goNextChapter,
    goPrevChapter,
  }
}

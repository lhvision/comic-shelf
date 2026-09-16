/**
 * @file useReaderNavigation.ts
 * @description 阅读器多屏滚动定位、进度计算与跨章节导航组合式函数。
 *
 * 核心职责：
 * 1. 物理视口滚动（`scrollToGroup`）：支持横向与竖向、smooth/instant 平滑过渡；
 * 2. 交互式切页跳转（`goToGroup` / `goToPage` / `prevGroup` / `nextGroup`）；
 * 3. 滚动进度换算（`onScroll`）：支持 LTR 与 RTL 反向进度，以及最邻近 Spread 自动吸附探测；
 * 4. 横向滚轮分屏步进（`onWheel`）：拦截纵向滚轮转为离散分屏平滑步进，放行触控板水平原生滑动；
 * 5. 前后环视预热（`preloadAround`）：在后台预加载当前页邻近的前后屏图片；
 * 6. 跨章节边界切入（`goNextChapter` / `goPrevChapter`）：自动维护 `?chapter=` 作用域与 URL 替换。
 */

import {
  getCurrentScope,
  nextTick,
  onScopeDispose,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue'
import type { Router } from 'vue-router'
import { useDebounceFn, useTimeoutFn } from '@vueuse/core'
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
 * 局部邻域探测 + 二分查找收敛：定位当前视口最临近的分屏分组索引。
 * 彻底消除 querySelectorAll 全表扫描与 900+ 节点 offsetTop 强制同步重排 (PITFALLS #86)。
 *
 * @param el 滚动容器 DOM
 * @param position 当前滚动距离（scrollTop 或 scrollLeft）
 * @param max 最大可滚动距离
 * @param horizontal 是否为横向排版
 * @param currentIdx 当前活跃分组索引
 * @param lastIdx 最后一组分组索引
 * @param isContinuous 是否为竖向连续条漫模式
 */
function resolveNearestGroupIndex(
  el: HTMLElement,
  position: number,
  max: number,
  horizontal: boolean,
  currentIdx: number,
  lastIdx: number,
  isContinuous: boolean,
  rtl = false,
): number {
  if (isContinuous) {
    const readLine = position + el.clientHeight * 0.4

    // 1. 局部邻域极速探测（针对平滑连续滚动，99% 命中当前页或前后 2 页，仅需 1~3 次轻量查询）
    const probeCandidates = [
      currentIdx,
      currentIdx + 1,
      currentIdx - 1,
      currentIdx + 2,
      currentIdx - 2,
    ]
    for (const idx of probeCandidates) {
      if (idx < 0 || idx > lastIdx) continue
      const spread = el.querySelector<HTMLElement>(`[data-group-index="${idx}"]`)
      if (!spread) continue
      const top = spread.offsetTop
      const bottom = top + spread.offsetHeight
      if (readLine >= top && readLine <= bottom) {
        return idx
      }
    }

    // 2. 大跨度跳转（拖拽滚动条滑块）：先以滚动百分比插值估算基准
    if (max > 0) {
      const ratio = rtl ? 1 - position / max : position / max
      const estimated = Math.max(0, Math.min(lastIdx, Math.round(ratio * lastIdx)))
      const estimatedCandidates = [
        estimated,
        estimated - 1,
        estimated + 1,
        estimated - 2,
        estimated + 2,
      ]
      for (const idx of estimatedCandidates) {
        if (idx < 0 || idx > lastIdx) continue
        const spread = el.querySelector<HTMLElement>(`[data-group-index="${idx}"]`)
        if (!spread) continue
        const top = spread.offsetTop
        const bottom = top + spread.offsetHeight
        if (readLine >= top && readLine <= bottom) {
          return idx
        }
      }
    }

    // 3. 二分查找终极收敛（千页规模下最多仅探测 log2(N) ≈ 10 次，绝无全量 O(N) 重排）
    let low = 0
    let high = lastIdx
    let bestIdx = currentIdx
    let bestDist = Number.POSITIVE_INFINITY

    while (low <= high) {
      const mid = Math.floor((low + high) / 2)
      const spread = el.querySelector<HTMLElement>(`[data-group-index="${mid}"]`)
      if (!spread) {
        break
      }
      const top = spread.offsetTop
      const bottom = top + spread.offsetHeight
      if (readLine >= top && readLine <= bottom) {
        return mid
      }
      const midCenter = top + spread.offsetHeight / 2
      const dist = Math.abs(midCenter - readLine)
      if (dist < bestDist) {
        bestDist = dist
        bestIdx = mid
      }
      if (readLine < top) {
        high = mid - 1
      } else {
        low = mid + 1
      }
    }
    return bestIdx
  }

  // 翻页模式（竖向翻页 / 横向翻页）：最临近单屏吸附
  const probeCandidates = [
    currentIdx,
    currentIdx + 1,
    currentIdx - 1,
    currentIdx + 2,
    currentIdx - 2,
  ]
  let bestDist = Number.POSITIVE_INFINITY
  let bestIdx = currentIdx

  for (const idx of probeCandidates) {
    if (idx < 0 || idx > lastIdx) continue
    const spread = el.querySelector<HTMLElement>(`[data-group-index="${idx}"]`)
    if (!spread) continue
    const spreadPos = horizontal ? spread.offsetLeft : spread.offsetTop
    const dist = Math.abs(spreadPos - position)
    if (dist < bestDist) {
      bestDist = dist
      bestIdx = idx
    }
  }

  // 大跨度跳转（拖动滚动条或大幅滑跃）兜底：偏移越出半屏时根据位置估算
  const pageSize = horizontal ? el.clientWidth : el.clientHeight
  if (bestDist > pageSize * 0.5 && max > 0) {
    const ratio = rtl ? 1 - position / max : position / max
    const estimated = Math.max(0, Math.min(lastIdx, Math.round(ratio * lastIdx)))
    const estimatedCandidates = [estimated, estimated - 1, estimated + 1]
    for (const idx of estimatedCandidates) {
      if (idx < 0 || idx > lastIdx) continue
      const spread = el.querySelector<HTMLElement>(`[data-group-index="${idx}"]`)
      if (!spread) continue
      const spreadPos = horizontal ? spread.offsetLeft : spread.offsetTop
      const dist = Math.abs(spreadPos - position)
      if (dist < bestDist) {
        bestDist = dist
        bestIdx = idx
      }
    }
  }

  return bestIdx
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

  /** 条漫无缝模式下右下角浮动页标活跃状态（滚动时感应唤醒，静止 1.5 秒后淡出） */
  const pillActive = ref(false)
  const { start: startPillHide, stop: stopPillHide } = useTimeoutFn(
    () => {
      pillActive.value = false
    },
    1500,
    { immediate: false },
  )

  function triggerPill() {
    pillActive.value = true
    stopPillHide()
    startPillHide()
  }

  /**
   * 标记是否处于程序化跳转（如点击翻页、外部直达、滑块跳转）的滑行期。
   * 在此期间阻止 handleScroll 被动探测中间态并反向抢占当前页码，根除页码跳动抖动死锁。
   */
  const isProgrammaticScrolling = ref(false)
  let programmaticTimer: ReturnType<typeof setTimeout> | null = null

  function lockProgrammaticScroll(durationMs = 320) {
    isProgrammaticScrolling.value = true
    if (programmaticTimer !== null) {
      clearTimeout(programmaticTimer)
    }
    programmaticTimer = setTimeout(() => {
      isProgrammaticScrolling.value = false
      programmaticTimer = null
    }, durationMs)
  }

  function unlockProgrammaticScroll() {
    if (isProgrammaticScrolling.value) {
      isProgrammaticScrolling.value = false
      if (programmaticTimer !== null) {
        clearTimeout(programmaticTimer)
        programmaticTimer = null
      }
    }
  }

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

    // 跨度判定：当跳转跨度超过 5 个分屏分组时（如外部直达、Home/End、跳章），退化为即时跳转，
    // 避免几十万像素漫长平滑滚动导致浏览器合成器压力以及中途 320ms 静音锁提前超时
    const groupDiff = Math.abs(groupIndex - currentGroupIndex.value)
    const effectiveBehavior: ScrollBehavior =
      groupDiff > 5 && behavior === 'smooth' ? 'auto' : behavior

    lockProgrammaticScroll(
      effectiveBehavior === 'instant' || effectiveBehavior === 'auto' ? 480 : 400,
    )

    if (typeof window !== 'undefined' && 'onscrollend' in window) {
      el.addEventListener('scrollend', unlockProgrammaticScroll, { once: true })
    }

    if (settings.mode === 'horizontal') {
      el.scrollTo({ left: target.offsetLeft, top: 0, behavior: effectiveBehavior })
    } else {
      el.scrollTo({ left: 0, top: target.offsetTop, behavior: effectiveBehavior })
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
    void nextTick(() => {
      recalibrateTargetOffset(clamped)
    })
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
    void nextTick(() => {
      recalibrateTargetOffset(groupIndex)
    })
    showChromeTemporarily()
    resetAutoTurnCountdown()
  }

  /** 翻到上一屏 */
  function prevGroup(behavior: ScrollBehavior = 'smooth') {
    goToGroup(currentGroupIndex.value - 1, behavior)
  }

  /** 翻到下一屏 */
  function nextGroup(behavior: ScrollBehavior = 'smooth') {
    goToGroup(currentGroupIndex.value + 1, behavior)
  }

  let scrollRafId: number | null = null
  let wheelCooldown = false
  let wheelCooldownTimer: ReturnType<typeof setTimeout> | null = null
  let accumulatedWheelDelta = 0
  let wheelResetTimer: ReturnType<typeof setTimeout> | null = null

  const WHEEL_THRESHOLD = 40
  const WHEEL_COOLDOWN_MS = 220

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (scrollRafId !== null) {
        cancelAnimationFrame(scrollRafId)
        scrollRafId = null
      }
      if (wheelCooldownTimer !== null) {
        clearTimeout(wheelCooldownTimer)
        wheelCooldownTimer = null
      }
      if (wheelResetTimer !== null) {
        clearTimeout(wheelResetTimer)
        wheelResetTimer = null
      }
      if (programmaticTimer !== null) {
        clearTimeout(programmaticTimer)
        programmaticTimer = null
      }
      preloadAround.cancel?.()
      stopPillHide()
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

    // 处于程序化跳转平滑滑行期：仅更新滚动进度条 progressValue，禁止被动探测反向抢占当前页码
    if (isProgrammaticScrolling.value) {
      return
    }

    let nearest = currentGroupIndex.value
    const lastIdx = Math.max(0, lastGroupIndex.value)

    // 1. 绝对边界钳制：若已抵达物理底端/顶端安全区，确定性夹紧至首末分屏
    if (rtl) {
      if (position <= 24) {
        nearest = lastIdx
      } else if (max > 0 && position >= max - 24) {
        nearest = 0
      }
    } else {
      if (max > 0 && position >= max - 24) {
        nearest = lastIdx
      } else if (position <= 16) {
        nearest = 0
      }
    }

    // 2. 非极端边界时：局部邻域探测 + 二分查找收敛（彻底消灭 900+ 节点每帧 O(N) 重排循环，PITFALLS #86）
    const isAtBoundary = rtl
      ? position <= 24 || (max > 0 && position >= max - 24)
      : position <= 16 || (max > 0 && position >= max - 24)

    if (!isAtBoundary && lastIdx > 0) {
      nearest = resolveNearestGroupIndex(
        el,
        position,
        max,
        horizontal,
        currentGroupIndex.value,
        lastIdx,
        settings.mode === 'vertical-continuous',
        rtl,
      )
    }

    if (Number.isFinite(nearest) && nearest !== currentGroupIndex.value) {
      currentGroupIndex.value = nearest
      currentPage.value = groupFirstPage(nearest)
    }

    if (!settings.autoTurn && settings.mode !== 'vertical-continuous') {
      showChromeTemporarily()
    }
    if (settings.mode === 'vertical-continuous' && settings.seamless) {
      triggerPill()
    }
    if (settings.mode !== 'vertical-continuous') {
      resetAutoTurnCountdown()
    }
  }

  /**
   * 在横向翻页排版下拦截纵向鼠标滚轮，执行离散分屏平滑步进；
   * 对水平为主的手势（触控板滑动或倾斜滚轮）放行原生物理滚动。
   *
   * @param event 滚轮事件对象
   */
  function onWheel(event: WheelEvent) {
    unlockProgrammaticScroll()
    if (settings.mode !== 'horizontal') return
    const el = scrollEl.value
    if (!el) return

    // 触控板水平手势或倾斜滚轮放行原生滚动
    if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return

    // 放行浏览器原生页面缩放手势（Ctrl/Cmd + 滚轮 或 触控板双指捏合）
    if (event.ctrlKey || event.metaKey) return

    event.preventDefault()

    if (wheelResetTimer !== null) {
      clearTimeout(wheelResetTimer)
      wheelResetTimer = null
    }

    if (wheelCooldown) return

    const factor = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 100 : 1
    accumulatedWheelDelta += event.deltaY * factor

    if (Math.abs(accumulatedWheelDelta) >= WHEEL_THRESHOLD) {
      const isDown = accumulatedWheelDelta > 0
      accumulatedWheelDelta = 0
      wheelCooldown = true

      if (isDown) {
        nextGroup()
      } else {
        prevGroup()
      }

      wheelCooldownTimer = setTimeout(() => {
        wheelCooldown = false
        wheelCooldownTimer = null
      }, WHEEL_COOLDOWN_MS)
    } else {
      wheelResetTimer = setTimeout(() => {
        accumulatedWheelDelta = 0
        wheelResetTimer = null
      }, 150)
    }
  }

  const preloadedPages = new Set<number>()
  watch([source, sourceId], () => {
    preloadedPages.clear()
  })

  /** 预加载当前页前后相邻分组的图片资源到浏览器磁盘/内存缓存（防抖 150ms 避免读者高速拖拽滚动条时途经大量页码瞬发海量无效预取） */
  const preloadAround = useDebounceFn((page: number) => {
    if (typeof Image === 'undefined') return
    const groupIndex = groupIndexForPage(page)
    const startGroup = Math.max(0, groupIndex - 1)
    const endGroup = Math.min(pageGroups.value.length - 1, groupIndex + 1)
    for (let group = startGroup; group <= endGroup; group += 1) {
      if (group === groupIndex) continue
      for (const targetPage of pageGroups.value[group] ?? []) {
        if (preloadedPages.has(targetPage)) continue
        preloadedPages.add(targetPage)
        const image = new Image()
        image.src = pageFileUrl(source.value, sourceId.value, targetPage)
      }
    }

    // 体验优化（Suggestion 4）：当读者抵达当前话后段（倒数 2 屏以内）且存在下一话时，静默预热下一话首屏画页
    const lastIdx = pageGroups.value.length - 1
    if (nextChapter.value && lastIdx >= 0 && groupIndex >= lastIdx - 1) {
      const nextStart = nextChapter.value.start
      const nextCount = nextChapter.value.page_count
      const warmupPages = [nextStart, nextStart + 1].filter((p) => p < nextStart + nextCount)
      for (const targetPage of warmupPages) {
        if (preloadedPages.has(targetPage)) continue
        preloadedPages.add(targetPage)
        const image = new Image()
        image.src = pageFileUrl(source.value, sourceId.value, targetPage)
      }
    }
  }, 150)

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

  /**
   * 纵向连续模式下在图片异步加载撑高后，微调视口位置以消除排版位移
   * @param groupIndex 目标分屏索引
   */
  function recalibrateTargetOffset(groupIndex: number) {
    const el = scrollEl.value
    if (!el || settings.mode !== 'vertical-continuous') return
    const target = el.querySelector<HTMLElement>(`[data-group-index="${groupIndex}"]`)
    if (!target) return
    if (Math.abs(el.scrollTop - target.offsetTop) > 8) {
      el.scrollTo({ left: 0, top: target.offsetTop, behavior: 'instant' })
    }
  }

  /**
   * 离散翻页模式自动切换推进逻辑：推进至下一分屏分组
   */
  function advanceAutoTurn(reduced = false) {
    if (settings.mode === 'vertical-continuous') return
    const nextIndex = Math.min(currentGroupIndex.value + 1, lastGroupIndex.value)
    currentGroupIndex.value = nextIndex
    currentPage.value = groupFirstPage(nextIndex)
    const behavior: ScrollBehavior = reduced ? 'auto' : 'smooth'
    scrollToGroup(nextIndex, behavior)
  }

  return {
    progressValue,
    pillActive,
    scrollToGroup,
    recalibrateTargetOffset,
    goToGroup,
    goToPage,
    prevGroup,
    nextGroup,
    advanceAutoTurn,
    onScroll,
    onWheel,
    preloadAround,
    setScope,
    goNextChapter,
    goPrevChapter,
    lockProgrammaticScroll,
    unlockProgrammaticScroll,
    isProgrammaticScrolling,
  }
}

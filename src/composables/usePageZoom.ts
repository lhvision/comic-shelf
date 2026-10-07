/**
 * @file usePageZoom.ts
 * @description 阅读器画页双击放大、防脱轨边界平移与视图还原状态机。
 *
 * 领域概念（GLOSSARY.md）：
 * - 画页放大（Page Zoom）：双击画页以点击坐标为中心 2.5 倍平滑放大，并允许拖拽平移浏览细节。
 * - 还原视图（Reset Zoom）：放大状态下将画页复原至 1:1 原始排版尺标。
 *
 * 核心契约：
 * 1. 双击/双触目标点智能对焦（基于点击位置瞬时偏置计算）；
 * 2. 防脱轨平移约束（Edge Clamping）：平移位移严格受限于画面有效范围，杜绝拖出视口露底；
 * 3. 放大态独占手势，隔离整书切页与滚动，避免阅读微小文字时发生误触；
 * 4. 支持悬浮还原胶囊按钮、再次双击、Escape 键或切页时自动还原。
 */

import { computed, ref, type CSSProperties, type Ref } from 'vue'
import { tryOnScopeDispose, useEventListener } from '@vueuse/core'

export interface PageFrameDimensions {
  w: number
  h: number
}

export interface UsePageZoomOptions {
  /** 放大倍率（默认 2.5x） */
  scale?: number
  /** 放大或还原状态变动时的回调通知（如通知外部压制跨话横幅） */
  onZoomChange?: (isZoomed: boolean) => void
}

export interface UsePageZoomReturn {
  /** 当前处于放大态的画页页号（无则为 null） */
  zoomedPage: Ref<number | null>
  /** 是否正处于放大状态 */
  isZoomed: Ref<boolean>
  /** 当前放大平移偏移量 */
  panOffset: Ref<{ x: number; y: number }>
  /** 是否正在执行指针拖拽平移 */
  isDragging: Ref<boolean>
  /** 放大倍率数值 */
  scale: number
  /** 切换指定画页的放大/还原状态 */
  toggleZoom: (
    page: number,
    clickPos?: { clientX: number; clientY: number },
    frameEl?: HTMLElement | null,
  ) => void
  /** 还原画页至 1:1 原始比例 */
  resetZoom: () => void
  /** 获取指定画页的缩放与平移内联样式 */
  getPageZoomStyle: (page: number) => CSSProperties | undefined
  /** 微调平移放大的画页视口（用于键盘上下左右与滚轮滚动，支持瞬时无过渡平移） */
  panBy: (deltaX: number, deltaY: number, instant?: boolean) => void
  /** 最近一段时间内（默认 450ms）是否刚刚切换过缩放，用于屏蔽连带的原生 click 事件 */
  wasRecentlyToggled: (threshold?: number) => boolean
  /** 画页双击事件处理函数（PC 端） */
  onPageDblClick: (page: number, event: MouseEvent) => void
  /** 画页指针按下处理函数（启动平移或识别移动端双触） */
  onPagePointerDown: (page: number, event: PointerEvent) => void
  /** 画页指针移动处理函数（执行平移拖动） */
  onPagePointerMove: (page: number, event: PointerEvent) => void
  /** 画页指针抬起处理函数（结束平移并结算双击） */
  onPagePointerUp: (page: number, event: PointerEvent) => void
  /** 画页指针取消处理函数 */
  onPagePointerCancel: (page: number, event: PointerEvent) => void
}

/**
 * 边界截断函数，保证数值严格落在 [min, max] 区间内
 */
function clamp(val: number, min: number, max: number): number {
  if (val < min) return min
  if (val > max) return max
  return val
}

/**
 * 画页局部放大与拖拽平移组合式函数
 */
export function usePageZoom(options: UsePageZoomOptions = {}): UsePageZoomReturn {
  const scale = options.scale ?? 2.5
  const zoomedPage = ref<number | null>(null)
  const isZoomed = computed(() => zoomedPage.value !== null)

  const panOffset = ref({ x: 0, y: 0 })
  const isDragging = ref(false)
  const isInstantPanning = ref(false)
  let instantPanResetTimer: ReturnType<typeof setTimeout> | null = null

  // 记录放大画页的物理尺寸以计算防脱轨平移最大边界
  const currentFrameDim = ref<PageFrameDimensions>({ w: 0, h: 0 })

  // 拖拽起始点追踪
  let dragStartClientX = 0
  let dragStartClientY = 0
  let dragStartPanX = 0
  let dragStartPanY = 0

  // 触控单次手势位移追踪（杜绝滑动误判为双击）
  let pointerDownClientX = 0
  let pointerDownClientY = 0

  // 移动端双触（Double-tap）检测状态机
  let lastTapTime = 0
  let lastTapPage = 0
  let lastTapX = 0
  let lastTapY = 0
  let lastToggleTime = 0

  /**
   * 计算当前画页在 scale 放大下的最大允许平移位移（保持边缘不脱轨）
   */
  function getMaxPan(dim: PageFrameDimensions) {
    const maxX = Math.max(0, ((scale - 1) * dim.w) / 2)
    const maxY = Math.max(0, ((scale - 1) * dim.h) / 2)
    return { maxX, maxY }
  }

  /**
   * 还原画页至 1:1 状态
   */
  function resetZoom() {
    if (zoomedPage.value === null) return
    zoomedPage.value = null
    panOffset.value = { x: 0, y: 0 }
    isDragging.value = false
    isInstantPanning.value = false
    if (instantPanResetTimer) {
      clearTimeout(instantPanResetTimer)
      instantPanResetTimer = null
    }
    options.onZoomChange?.(false)
  }

  /**
   * 微调平移放大的画页视口（用于键盘上下左右与滚轮滚动）
   * @param instant 是否瞬时生效，滚轮高频滚动或长按方向键连击时传入 true 屏蔽 CSS 缓动延迟
   */
  function panBy(deltaX: number, deltaY: number, instant = false) {
    if (!isZoomed.value) return
    if (instant) {
      isInstantPanning.value = true
      if (instantPanResetTimer) {
        clearTimeout(instantPanResetTimer)
      }
      instantPanResetTimer = setTimeout(() => {
        isInstantPanning.value = false
        instantPanResetTimer = null
      }, 120)
    } else {
      isInstantPanning.value = false
    }

    const { maxX, maxY } = getMaxPan(currentFrameDim.value)
    panOffset.value = {
      x: clamp(panOffset.value.x + deltaX, -maxX, maxX),
      y: clamp(panOffset.value.y + deltaY, -maxY, maxY),
    }
  }

  function wasRecentlyToggled(threshold = 450): boolean {
    return Date.now() - lastToggleTime < threshold
  }

  /**
   * 检查事件是否发生在真实的漫画图片区域内部（过滤掉左右或上下的黑边留白）
   */
  function isEventOnImage(event: MouseEvent | PointerEvent, page: number): boolean {
    const target = event.target as HTMLElement | null
    // 1. 若 target 位于图片、图片容器或覆盖层气泡内，直判命中
    if (target?.closest('.comic-page-img, .comic-page-img-frame, .reader-bubble-overlay')) {
      return true
    }

    // 2. 几何矩形判定：以该页真实图片 DOM 边界为准
    if (typeof document !== 'undefined') {
      const imgEl =
        document.querySelector<HTMLElement>(`#page-${page} .comic-page-img-frame`) ||
        document.querySelector<HTMLElement>(`#page-${page} .comic-page-img`)
      if (imgEl) {
        const rect = imgEl.getBoundingClientRect()
        return (
          event.clientX >= rect.left &&
          event.clientX <= rect.right &&
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom
        )
      }
    }

    return false
  }

  /**
   * 切换画页放大状态
   */
  function toggleZoom(
    page: number,
    clickPos?: { clientX: number; clientY: number },
    frameEl?: HTMLElement | null,
  ) {
    lastToggleTime = Date.now()

    // 若当前已在放大态，且点击的是同一页，则执行复位还原
    if (zoomedPage.value === page) {
      resetZoom()
      return
    }

    // 测量目标画页元素的尺寸，优先选择真实图片元素（排除外围黑边干扰）
    let w = 400
    let h = 600
    let initialPanX = 0
    let initialPanY = 0

    let el = frameEl
    if (typeof document !== 'undefined') {
      el =
        document.querySelector<HTMLElement>(`#page-${page} .comic-page-img-frame`) ||
        document.querySelector<HTMLElement>(`#page-${page} .comic-page-img`) ||
        frameEl ||
        document.querySelector<HTMLElement>(`#page-${page} .page-frame`) ||
        document.getElementById(`page-${page}`)
    }

    if (el) {
      const rect = el.getBoundingClientRect()
      if (rect.width > 0 && rect.height > 0) {
        w = rect.width
        h = rect.height
      }

      if (clickPos && w > 0 && h > 0) {
        // 计算点击点相对图片真实区域左上角的物理坐标
        const clickX = clickPos.clientX - rect.left
        const clickY = clickPos.clientY - rect.top

        // 将点击的目标位置对焦到视口中央
        const rawPanX = (w / 2 - clickX) * scale
        const rawPanY = (h / 2 - clickY) * scale

        const { maxX, maxY } = getMaxPan({ w, h })
        initialPanX = clamp(rawPanX, -maxX, maxX)
        initialPanY = clamp(rawPanY, -maxY, maxY)
      }
    }

    currentFrameDim.value = { w, h }
    panOffset.value = { x: initialPanX, y: initialPanY }
    isDragging.value = false
    zoomedPage.value = page
    options.onZoomChange?.(true)
  }

  function onPageDblClick(page: number, event: MouseEvent) {
    // 屏蔽可能在 450ms 内由 pointerup 刚触发过的双击，杜绝重复切换
    if (Date.now() - lastToggleTime < 450) return

    // 未放大时，若双击发生在黑色留空区域，直接忽略，严禁触发放大
    if (zoomedPage.value !== page && !isEventOnImage(event, page)) {
      return
    }

    toggleZoom(
      page,
      { clientX: event.clientX, clientY: event.clientY },
      event.currentTarget as HTMLElement | null,
    )
  }

  function onPagePointerDown(page: number, event: PointerEvent) {
    if (
      (event.button ?? 0) !== 0 ||
      (event.pointerType === 'touch' && (event.isPrimary ?? true) === false)
    ) {
      return
    }

    pointerDownClientX = event.clientX
    pointerDownClientY = event.clientY

    if (zoomedPage.value === page) {
      isDragging.value = true
      dragStartClientX = event.clientX
      dragStartClientY = event.clientY
      dragStartPanX = panOffset.value.x
      dragStartPanY = panOffset.value.y

      const target = event.currentTarget as HTMLElement | null
      try {
        target?.setPointerCapture(event.pointerId)
      } catch {
        // ignore capture failure on unsupported environments
      }
      event.stopPropagation?.()
    }
  }

  function onPagePointerMove(page: number, event: PointerEvent) {
    if (zoomedPage.value === page && isDragging.value) {
      const deltaX = event.clientX - dragStartClientX
      const deltaY = event.clientY - dragStartClientY

      const { maxX, maxY } = getMaxPan(currentFrameDim.value)
      panOffset.value = {
        x: clamp(dragStartPanX + deltaX, -maxX, maxX),
        y: clamp(dragStartPanY + deltaY, -maxY, maxY),
      }
      event.stopPropagation?.()
    }
  }

  function onPagePointerUp(page: number, event: PointerEvent) {
    if (
      (event.button ?? 0) !== 0 ||
      (event.pointerType === 'touch' && (event.isPrimary ?? true) === false)
    ) {
      return
    }

    let hadDrag = false
    if (zoomedPage.value === page && isDragging.value) {
      isDragging.value = false
      const dragDist = Math.hypot(
        event.clientX - dragStartClientX,
        event.clientY - dragStartClientY,
      )
      hadDrag = dragDist > 6
      const target = event.currentTarget as HTMLElement | null
      try {
        target?.releasePointerCapture(event.pointerId)
      } catch {
        // ignore
      }
      event.stopPropagation?.()
    } else {
      // 未放大状态下：若单次触控过程位移超过 12px（即发生了滑动或滚动手势），则不作为有效点击/双触候选
      const downDist = Math.hypot(
        event.clientX - pointerDownClientX,
        event.clientY - pointerDownClientY,
      )
      hadDrag = downDist > 12
    }

    // 若刚刚发生了明显拖拽平移或滑动手势，不记录为 tap 候选，杜绝拖拽后误判双触
    if (hadDrag) {
      lastTapTime = 0
      return
    }

    // 移动端双触（Double-tap）启发式检测
    const now = Date.now()
    const timeDiff = now - lastTapTime
    const dist = Math.hypot(event.clientX - lastTapX, event.clientY - lastTapY)

    if (page === lastTapPage && timeDiff > 40 && timeDiff < 320 && dist < 28) {
      lastTapTime = 0
      // 未放大时，若双触发生在黑色留空区域，直接忽略，严禁触发放大
      if (zoomedPage.value !== page && !isEventOnImage(event, page)) {
        return
      }

      toggleZoom(
        page,
        { clientX: event.clientX, clientY: event.clientY },
        event.currentTarget as HTMLElement | null,
      )
      return
    }

    // 仅在点击发生在图像区域内部或当前已处于放大态时，才记录为双触候选 tap（放大态允许双击黑边自愈还原）
    if (isEventOnImage(event, page) || zoomedPage.value === page) {
      lastTapTime = now
      lastTapPage = page
      lastTapX = event.clientX
      lastTapY = event.clientY
    } else {
      lastTapTime = 0
    }
  }

  function onPagePointerCancel(page: number, event: PointerEvent) {
    lastTapTime = 0
    if (zoomedPage.value === page && isDragging.value) {
      isDragging.value = false
      const target = event.currentTarget as HTMLElement | null
      try {
        target?.releasePointerCapture(event.pointerId)
      } catch {
        // ignore
      }
    }
  }

  function getPageZoomStyle(page: number): CSSProperties | undefined {
    if (zoomedPage.value === page) {
      return {
        transform: `translate3d(${panOffset.value.x}px, ${panOffset.value.y}px, 0) scale(${scale})`,
        transformOrigin: 'center center',
        transition:
          isDragging.value || isInstantPanning.value
            ? 'none'
            : 'transform var(--duration-2) var(--ease-out)',
        zIndex: 20,
        touchAction: 'none',
        cursor: isDragging.value ? 'grabbing' : 'grab',
      }
    }
    if (isZoomed.value) {
      return {
        opacity: 0.35,
        pointerEvents: 'none',
        transition: 'opacity var(--duration-2) var(--ease-out)',
      }
    }
    return undefined
  }

  function onResize() {
    if (isZoomed.value) {
      resetZoom()
    }
  }

  tryOnScopeDispose(() => {
    if (instantPanResetTimer) {
      clearTimeout(instantPanResetTimer)
      instantPanResetTimer = null
    }
  })

  useEventListener(typeof window !== 'undefined' ? window : null, 'resize', onResize)

  return {
    zoomedPage,
    isZoomed,
    panOffset,
    isDragging,
    scale,
    toggleZoom,
    resetZoom,
    getPageZoomStyle,
    panBy,
    wasRecentlyToggled,
    onPageDblClick,
    onPagePointerDown,
    onPagePointerMove,
    onPagePointerUp,
    onPagePointerCancel,
  }
}

/**
 * @file useReaderBubble.ts
 * @description 阅读器对白气泡呼吸高亮与台词直达定位组合式函数。
 *
 * 核心契约：
 * 1. 从 URL Query 与路由参数中解析目标高亮气泡：
 *    - `page` (通过 query 或 params 指定)
 *    - `bubble_box`: 归一化百分比坐标 `[ymin, xmin, ymax, xmax]` ∈ [0, 1]，例如 `0.1,0.2,0.3,0.4`
 *    - `highlight_bubble` / `bubble`: 声明式高亮开关（如 `1` 或 `true`），缺省 box 时回退至典藏基准分镜对白框 `[0.12, 0.45, 0.28, 0.68]`
 *    - `bubble_text` / `text`: 命中台词文本摘要
 * 2. 暴露 `targetBubble` 与 `targetPage`，无缝驱动视口滚动与气泡呼吸高亮覆盖层。
 */

import { computed, ref, watch, type ComputedRef } from 'vue'
import { useRoute, useRouter, type RouteLocationNormalizedLoaded, type Router } from 'vue-router'
import { useTimeoutFn } from '@vueuse/core'

/**
 * 目标气泡高亮数据结构
 */
export interface TargetBubble {
  /** 气泡所属漫画全局页码 (1-based) */
  page: number
  /** 归一化百分比矩形 [ymin, xmin, ymax, xmax]，各分量 ∈ [0, 1] */
  box: [number, number, number, number]
  /** 命中对白文本摘要（可选） */
  text?: string
}

/**
 * `useReaderBubble` 返回值契约
 */
export interface UseReaderBubbleReturn {
  /** 目标气泡数据（若无或已淡出抹除则为 null） */
  targetBubble: ComputedRef<TargetBubble | null>
  /** URL 中指定的直接跳转目标页码（若无有效页码则为 null） */
  targetPage: ComputedRef<number | null>
  /** 手动或自动消除气泡高亮并原地静默擦除 URL 中的气泡参数 */
  dismissBubble: () => void
}

/**
 * 缺省气泡坐标基准：与 docs/AI_ECOSYSTEM_ROADMAP.md 标准 Schema 对齐
 */
export const DEFAULT_BUBBLE_BOX: [number, number, number, number] = [0.12, 0.45, 0.28, 0.68]

/**
 * 解析并归一化 bubble_box 字符串
 * @param raw 原始字符串，支持 "0.1,0.2,0.3,0.4" 或 "[0.1, 0.2, 0.3, 0.4]"
 * @returns 经过范围校验的 [ymin, xmin, ymax, xmax]，非法则返回 null
 */
export function parseBubbleBox(raw: unknown): [number, number, number, number] | null {
  if (typeof raw !== 'string') return null
  const cleaned = raw.replace(/[[\]]/g, '').trim()
  if (!cleaned) return null

  const parts = cleaned.split(/[\s,]+/).map((v) => Number.parseFloat(v))
  if (parts.length !== 4 || parts.some((v) => !Number.isFinite(v))) {
    return null
  }

  let [ymin, xmin, ymax, xmax] = parts as [number, number, number, number]

  // 若存在非负分量显著超出归一化区间（如 RapidOCR/Qwen2-VL 0..1000 或百分比 0..100），自适应归一化至 [0, 1]
  const maxVal = Math.max(ymin, xmin, ymax, xmax)
  if (parts.every((v) => v >= 0) && maxVal > 2) {
    const scale = maxVal > 100 ? 1000 : 100
    ymin /= scale
    xmin /= scale
    ymax /= scale
    xmax /= scale
  }

  // 坐标下限 0，上限 1
  const clampedYmin = Math.max(0, Math.min(1, ymin))
  const clampedXmin = Math.max(0, Math.min(1, xmin))
  const clampedYmax = Math.max(clampedYmin, Math.min(1, ymax))
  const clampedXmax = Math.max(clampedXmin, Math.min(1, xmax))

  return [clampedYmin, clampedXmin, clampedYmax, clampedXmax]
}

/**
 * 阅读器气泡定位 Hook
 * @param customRoute 可选自定义路由实例（便于单测与隔离测试）
 * @param customRouter 可选自定义路由导航实例
 */
export function useReaderBubble(
  customRoute?: RouteLocationNormalizedLoaded,
  customRouter?: Router,
): UseReaderBubbleReturn {
  const route = customRoute ?? useRoute()
  let router: Router | undefined = customRouter
  if (!router && !customRoute) {
    try {
      router = useRouter()
    } catch {
      // 兼容在非组件上下文中测试
    }
  }

  const isDismissed = ref(false)

  const dismissBubble = () => {
    if (isDismissed.value) return
    isDismissed.value = true

    if (
      router &&
      (route.query.bubble_box !== undefined ||
        route.query.bubble_text !== undefined ||
        route.query.highlight_bubble !== undefined ||
        route.query.bubble !== undefined)
    ) {
      const nextQuery = { ...route.query }
      delete nextQuery.bubble_box
      delete nextQuery.bubble_text
      delete nextQuery.highlight_bubble
      delete nextQuery.bubble
      void router.replace({ query: nextQuery })
    }
  }

  const { start: scheduleDismiss, stop: cancelDismiss } = useTimeoutFn(dismissBubble, 2800, {
    immediate: false,
  })

  watch(
    () => [
      route.query.bubble_box,
      route.query.bubble,
      route.query.highlight_bubble,
      route.query.page,
    ],
    ([box, b1, b2]) => {
      if (box || b1 || b2) {
        isDismissed.value = false
        cancelDismiss()
        scheduleDismiss()
      }
    },
    { immediate: true },
  )

  const targetPage = computed<number | null>(() => {
    const qPage = route.query.page
    const pPage = route.params.page
    const raw =
      typeof qPage === 'string' && qPage
        ? qPage
        : Array.isArray(qPage)
          ? qPage[0]
          : typeof pPage === 'string' && pPage
            ? pPage
            : Array.isArray(pPage)
              ? pPage[0]
              : null

    if (!raw) return null
    const num = Number(raw)
    return Number.isFinite(num) && num > 0 ? Math.floor(num) : null
  })

  const targetBubble = computed<TargetBubble | null>(() => {
    if (isDismissed.value) return null
    const page = targetPage.value
    if (!page) return null

    const boxParam = route.query.bubble_box
    const parsedBox = parseBubbleBox(boxParam)

    const isHighlightRequested =
      route.query.highlight_bubble === '1' ||
      route.query.highlight_bubble === 'true' ||
      route.query.bubble === '1' ||
      route.query.bubble === 'true'

    // 若未提供有效 box，且未显式请求高亮，则不渲染气泡
    if (!parsedBox && !isHighlightRequested) {
      return null
    }

    const box = parsedBox ?? DEFAULT_BUBBLE_BOX

    const rawText =
      typeof route.query.bubble_text === 'string'
        ? route.query.bubble_text
        : typeof route.query.text === 'string'
          ? route.query.text
          : undefined

    const text = rawText ? rawText.trim() : undefined

    return {
      page,
      box,
      ...(text ? { text } : {}),
    }
  })

  return {
    targetBubble,
    targetPage,
    dismissBubble,
  }
}

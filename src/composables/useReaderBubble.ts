/**
 * @file useReaderBubble.ts
 * @description 阅读器对白气泡呼吸高亮与台词直达定位组合式函数。
 *
 * 核心契约：
 * 1. 从 URL Query 与路由参数中解析目标高亮气泡：
 *    - `page` (通过 query 或 params 指定)
 *    - `bubble_box`: 归一化百分比坐标 `[ymin, xmin, ymax, xmax]` ∈ [0, 1]，例如 `0.1,0.2,0.3,0.4`
 *    - `bubble_boxes`: 同一页其余命中气泡坐标，`;` 分隔（如 `0.1,0.2,0.3,0.4;0.5,0.6,0.7,0.8`），
 *      只作静态描边，不参与定位与 callout
 *    - `highlight_bubble` / `bubble`: 声明式高亮开关（如 `1` 或 `true`），缺省 box 时回退至典藏基准分镜对白框 `[0.12, 0.45, 0.28, 0.68]`
 *    - `bubble_text` / `text`: 命中台词文本摘要
 * 2. 暴露 `targetBubble` 与 `targetPage`，无缝驱动视口滚动与气泡呼吸高亮覆盖层。
 */

import { computed, ref, watch, type ComputedRef } from 'vue'
import { useRoute, useRouter, type RouteLocationNormalizedLoaded, type Router } from 'vue-router'
import { useTimeoutFn } from '@vueuse/core'
import { clamp } from '@/utils/math'

/** 归一化百分比矩形 [ymin, xmin, ymax, xmax]，各分量 ∈ [0, 1] */
export type BubbleBox = [number, number, number, number]

/**
 * 目标气泡高亮数据结构
 */
export interface TargetBubble {
  /** 气泡所属漫画全局页码 (1-based) */
  page: number
  /** 归一化百分比矩形 [ymin, xmin, ymax, xmax]，各分量 ∈ [0, 1] */
  box: BubbleBox
  /** 命中对白文本摘要（可选） */
  text?: string
  /** 同页其余命中气泡，仅静态描边；代表格本身不在其中 */
  others?: BubbleBox[]
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
export const DEFAULT_BUBBLE_BOX: BubbleBox = [0.12, 0.45, 0.28, 0.68]

/**
 * 一页最多描几格（代表格 + 其余格）。与后端 `MAX_PAGE_BOXES` 同值：后端按此封顶
 * `other_boxes`，前端再按此封顶一次，防手改 URL 或 MCP 直接投喂超长参数刷出满屏框
 */
export const MAX_HIGHLIGHT_BOXES = 6

/**
 * 解析并归一化 bubble_box 字符串
 * @param raw 原始字符串，支持 "0.1,0.2,0.3,0.4" 或 "[0.1, 0.2, 0.3, 0.4]"
 * @returns 经过范围校验的 [ymin, xmin, ymax, xmax]，非法则返回 null
 */
export function parseBubbleBox(raw: unknown): BubbleBox | null {
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
  const clampedYmin = clamp(ymin, 0, 1)
  const clampedXmin = clamp(xmin, 0, 1)
  const clampedYmax = clamp(ymax, clampedYmin, 1)
  const clampedXmax = clamp(xmax, clampedXmin, 1)

  return [clampedYmin, clampedXmin, clampedYmax, clampedXmax]
}

/**
 * 解析 bubble_boxes 参数：同页其余命中气泡，`;` 分隔的多个四点坐标
 * @param raw URL query 原始值
 * @returns 合法气泡矩形数组，最多 `MAX_HIGHLIGHT_BOXES - 1` 组；
 *          单个畸形段被丢弃而不是整条放弃
 */
export function parseBubbleBoxes(raw: unknown): BubbleBox[] {
  if (typeof raw !== 'string' || !raw.trim()) return []
  return raw
    .split(';')
    .map((seg) => parseBubbleBox(seg))
    .filter((b): b is BubbleBox => b !== null)
    .slice(0, MAX_HIGHLIGHT_BOXES - 1)
}

/**
 * 气泡坐标 → URL 参数文本（4 位小数，逗号分隔）。与 parseBubbleBox 成对，
 * 编解码的合法性校验只留这一处定义，避免浮点位数与判废标准在两个方向上漂移
 * @param box 四点归一化坐标
 * @returns 编码后的参数文本；含非有限数值或点数不足时返回 null，由调用方决定跳过
 */
export function serializeBubbleBox(box: number[] | undefined): string | null {
  if (!Array.isArray(box) || box.length !== 4) return null
  const nums = box.map((v) => Number(v))
  if (!nums.every((v) => Number.isFinite(v))) return null
  return nums.map((v) => v.toFixed(4)).join(',')
}

/**
 * 同页其余气泡 → `bubble_boxes` 参数文本（`;` 分隔），非法段直接丢弃。
 * 与 parseBubbleBoxes 对称封顶：`maxItems` 只是 schema 声明、不构成运行时保证，
 * 不夹就会让 MCP 拼出画面封顶而地址栏不封顶的超长 URL
 * @param boxes 后端 other_boxes 原始值
 */
export function serializeBubbleBoxes(boxes: number[][] | undefined): string {
  return (boxes ?? [])
    .slice(0, MAX_HIGHLIGHT_BOXES - 1)
    .map(serializeBubbleBox)
    .filter((s): s is string => s !== null)
    .join(';')
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
        route.query.bubble_boxes !== undefined ||
        route.query.bubble_text !== undefined ||
        route.query.highlight_bubble !== undefined ||
        route.query.bubble !== undefined)
    ) {
      const nextQuery = { ...route.query }
      delete nextQuery.bubble_box
      delete nextQuery.bubble_boxes
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
      route.query.bubble_boxes,
      route.query.bubble,
      route.query.highlight_bubble,
      route.query.page,
    ],
    // 回调一律按名读取 route.query，绝不按位置解构源数组：源数组加一项就会让
    // 尾部参数静默掉出条件（曾导致 highlight_bubble 永不触发自动熄灭）
    () => {
      const q = route.query
      if (q.bubble_box || q.bubble_boxes || q.bubble || q.highlight_bubble) {
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

    const siblingBoxes = parseBubbleBoxes(route.query.bubble_boxes)

    // 代表格畸形时不能让同页其余格跟着消失（弹层已按「N 处命中」承诺过）：
    // 提升第一格合法坐标作代表格，剩余仍作静态描边；一格合法坐标都没有时，
    // 才退回 highlight 标记要求的兜底框
    if (!parsedBox && siblingBoxes.length === 0 && !isHighlightRequested) {
      return null
    }

    const box = parsedBox ?? siblingBoxes[0] ?? DEFAULT_BUBBLE_BOX
    const others = parsedBox ? siblingBoxes : siblingBoxes.slice(1)

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
      ...(others.length > 0 ? { others } : {}),
    }
  })

  return {
    targetBubble,
    targetPage,
    dismissBubble,
  }
}

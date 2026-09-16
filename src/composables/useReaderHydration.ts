/**
 * @file useReaderHydration.ts
 * @description 阅读器常驻骨架与非对称迟滞注水视窗 Composable。
 *
 * 核心职责：
 * 1. 动态自适应视窗（Adaptive Hydration Window）：
 *    - 借助 VueUse useDevicePixelRatio 与 useNetwork 感知设备与网络环境；
 *    - 弱网（2G/3G/saveData）时收敛前向预取；移动端或高 DPR 屏幕收敛显存预算；
 *    - 桌面高速宽带环境下维持充裕注水缓冲（前向 15 屏 + 后向 30 屏）；
 * 2. 宽高比定盘（Ratio Latching）：
 *    - 维护物理宽高比字典（pageRatios Map），避免批量图片解码就绪时高频触发全卷模板级联重算；
 *    - 挂载 defaultComicRatio 响应式 Ref 驱动未就绪纸本骨架（quiescent-paper）真实比例撑高；
 * 3. 目标气泡特权注水（Target Bubble Privilege）：
 *    - 台词检索定位等目标所在分组享有 O(1) 永久强制注水特权，确保 BoundingClientRect 定位绝对精准；
 * 4. 视窗判定（isGroupHydrated）：
 *    - 为分卷缩略卷轴（Filmstrip）、主画卷视口（ReaderViewport）、画中画悬停预览（Hover Preview）提供标准复用契约。
 */

import { computed, type Ref } from 'vue'
import { useDevicePixelRatio, useMediaQuery, useNetwork } from '@vueuse/core'
import type { TargetBubble } from '@/composables/useReaderBubble'
import { useComicRatioPool } from '@/composables/useComicRatioPool'

/**
 * 分屏页码分组定义
 */
export interface OrderedGroup {
  /** 当前分屏包含的全局页码列表 */
  pages: number[]
  /** 分屏分组原始索引（0-based） */
  index: number
}

/**
 * 自定义缓冲区覆盖配置
 */
export interface HydrationBufferConfig {
  /** 前向预热屏数（默认自适应 5~15） */
  forward?: number
  /** 后向驻留屏数（默认自适应 10~30） */
  backward?: number
}

/**
 * `useReaderHydration` 入参契约
 */
export interface UseReaderHydrationOptions {
  /** 排序后的分屏分组列表（Ref） */
  orderedGroups: Ref<OrderedGroup[]>
  /** 当前聚焦的分屏分组索引（0-based，Ref） */
  currentGroupIndex?: Ref<number | undefined>
  /** 漫画唯一业务标识（Ref，用于切换漫画时自动清空存量宽高比字典） */
  comicKey: Ref<string>
  /** 待高亮呈现的目标气泡（来自台词检索等直接定位，Ref） */
  targetBubble?: Ref<TargetBubble | null | undefined>
  /** 手动覆盖缓冲区大小（可选） */
  bufferOverride?: HydrationBufferConfig
}

/**
 * 掌管阅读器画卷注水视窗与宽高比定盘的统一状态驱动 Composable
 * @param options 入参选项配置
 * @returns 注水状态判定、样式生成、图片就绪回调与自适应缓冲大小
 */
export function useReaderHydration(options: UseReaderHydrationOptions) {
  const { orderedGroups, currentGroupIndex, comicKey, targetBubble, bufferOverride } = options

  // 1. 设备与网络环境自适应感知（VueUse 标准能力集成）
  const { pixelRatio } = useDevicePixelRatio()
  const { effectiveType, saveData } = useNetwork()
  const isMobile = useMediaQuery('(max-width: 768px)')

  const forwardBuffer = computed(() => {
    if (bufferOverride?.forward != null) return bufferOverride.forward
    // 弱网或开启省流模式
    if (saveData.value || effectiveType.value === '2g' || effectiveType.value === '3g') {
      return 5
    }
    // 移动端或超高 DPR 屏幕（缩减前向避免显存紧张）
    if (isMobile.value || pixelRatio.value >= 2.5) {
      return 8
    }
    // 桌面宽带环境默认 15 屏
    return 15
  })

  const backwardBuffer = computed(() => {
    if (bufferOverride?.backward != null) return bufferOverride.backward
    // 弱网或省流模式
    if (saveData.value || effectiveType.value === '2g' || effectiveType.value === '3g') {
      return 10
    }
    // 移动端或超高 DPR 屏幕
    if (isMobile.value || pixelRatio.value >= 2.5) {
      return 15
    }
    // 桌面宽带环境默认 30 屏
    return 30
  })

  const fullHydrationThreshold = computed(() => forwardBuffer.value + backwardBuffer.value)

  // 2. 物理宽高比锁盘池（集成漫画会话级共享池 useComicRatioPool，实现主视口、胶片轨与画中画跨视图零损耗互通）
  const { pageRatios, defaultComicRatio, setPageRatio, getPageStyle } = useComicRatioPool(comicKey)

  function onPageImageReady(page: number, ratio?: string | null) {
    setPageRatio(page, ratio)
  }

  // 3. 目标气泡特权保护（O(1) 预先计算目标分组）
  const targetBubbleGroupIndex = computed<number | null>(() => {
    const bubble = targetBubble?.value
    if (!bubble) return null
    const bubblePage = bubble.page
    const targetGroup = orderedGroups.value.find((g) => g.pages.includes(bubblePage))
    return targetGroup ? targetGroup.index : null
  })

  // 4. 核心注水判定算法
  function isGroupHydrated(groupIndex: number): boolean {
    const groups = orderedGroups.value
    // 4.1 全量注水安全阈值（总组数足够小时无需虚拟化）
    if (groups.length <= fullHydrationThreshold.value) {
      return true
    }

    // 4.2 特权保护：若存在目标气泡，所在分组永久注水
    if (targetBubbleGroupIndex.value === groupIndex) {
      return true
    }

    // 4.3 核心非对称迟滞滑动窗口
    const rawCur = currentGroupIndex?.value
    const cur = typeof rawCur === 'number' && Number.isFinite(rawCur) ? Math.max(0, rawCur) : 0
    const minIdx = Math.max(0, cur - backwardBuffer.value)
    const maxIdx = cur + forwardBuffer.value

    return groupIndex >= minIdx && groupIndex <= maxIdx
  }

  return {
    forwardBuffer,
    backwardBuffer,
    fullHydrationThreshold,
    isGroupHydrated,
    getPageStyle,
    onPageImageReady,
    defaultComicRatio,
    pageRatios,
  }
}

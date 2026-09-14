/**
 * @file useVaporBenchmark.ts
 * @description Vue 3.6 Vapor Mode vs VDOM 基准跑分沙盒逻辑状态机。
 *
 * 遵循红线 4（视图轻量化，逻辑全部下沉到 Composable）与红线 5（顶层精准解构）。
 */

import { ref, computed, nextTick } from 'vue'

export interface BenchItem {
  id: number
  title: string
  progress: number
  active: boolean
}

export interface BenchResult {
  timestamp: string
  mode: 'vdom' | 'vapor'
  itemCount: number
  mountMs: number
  patchAvgMs: number
  patchFps: number
  unmountMs: number
  heapMb?: number
}

export function useVaporBenchmark() {
  const mode = ref<'vdom' | 'vapor'>('vapor')
  const itemCount = ref<number>(1000)
  const items = ref<BenchItem[]>([])
  const isRunning = ref<boolean>(false)
  const isPatching = ref<boolean>(false)

  // 测量结果
  const mountDuration = ref<number | null>(null)
  const patchAvgDuration = ref<number | null>(null)
  const patchFps = ref<number | null>(null)
  const unmountDuration = ref<number | null>(null)
  const heapUsedMb = ref<number | null>(null)
  const history = ref<BenchResult[]>([])

  function readHeapMb(): number | undefined {
    const memory = (performance as { memory?: { usedJSHeapSize?: number } }).memory
    if (memory?.usedJSHeapSize) {
      return Math.round((memory.usedJSHeapSize / (1024 * 1024)) * 10) / 10
    }
    return undefined
  }

  /** 批量挂载测试 */
  async function runMountTest() {
    if (isRunning.value) return
    isRunning.value = true

    // 先清理
    items.value = []
    await nextTick()

    const count = itemCount.value
    const nextItems: BenchItem[] = Array.from({ length: count }, (_, i) => ({
      id: i + 1,
      title: `画卷藏本 · 册目 ${i + 1}`,
      progress: Math.floor(Math.random() * 100),
      active: i % 10 === 0,
    }))

    const t0 = performance.now()
    items.value = nextItems
    await nextTick()
    const t1 = performance.now()

    mountDuration.value = Math.round((t1 - t0) * 100) / 100
    heapUsedMb.value = readHeapMb() ?? null
    isRunning.value = false
  }

  /** 高频响应式补丁测试（60 次连续更新） */
  async function runPatchTest(ticks = 60) {
    if (isRunning.value || items.value.length === 0) return
    isRunning.value = true
    isPatching.value = true

    const frameDurations: number[] = []

    for (let round = 0; round < ticks; round++) {
      const t0 = performance.now()

      // 批量微粒变更
      for (let i = 0; i < items.value.length; i += 3) {
        const item = items.value[i]
        if (item) {
          item.progress = (item.progress + 5) % 101
          item.active = round % 2 === 0
        }
      }

      await nextTick()
      const t1 = performance.now()
      frameDurations.push(t1 - t0)

      // 释放微任务让浏览器排版
      await new Promise((r) => requestAnimationFrame(r))
    }

    const totalTime = frameDurations.reduce((acc, v) => acc + v, 0)
    const avgMs = totalTime / frameDurations.length
    patchAvgDuration.value = Math.round(avgMs * 100) / 100
    patchFps.value = Math.round(1000 / Math.max(avgMs, 0.1))

    isPatching.value = false
    isRunning.value = false
  }

  /** 卸载与内存回收测试 */
  async function runUnmountTest() {
    if (isRunning.value || items.value.length === 0) return
    isRunning.value = true

    const t0 = performance.now()
    items.value = []
    await nextTick()
    const t1 = performance.now()

    unmountDuration.value = Math.round((t1 - t0) * 100) / 100
    heapUsedMb.value = readHeapMb() ?? null
    isRunning.value = false

    // 记录本次基准数据
    if (mountDuration.value !== null) {
      history.value.unshift({
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        mode: mode.value,
        itemCount: itemCount.value,
        mountMs: mountDuration.value,
        patchAvgMs: patchAvgDuration.value ?? 0,
        patchFps: patchFps.value ?? 0,
        unmountMs: unmountDuration.value,
        heapMb: heapUsedMb.value ?? undefined,
      })
    }
  }

  /** 一键跑完整套测试 */
  async function runFullSuite() {
    await runMountTest()
    await new Promise((r) => setTimeout(r, 200))
    await runPatchTest(45)
    await new Promise((r) => setTimeout(r, 200))
    await runUnmountTest()
  }

  /** 生成并复制 Markdown 跑分报告 */
  async function copyReport(): Promise<boolean> {
    if (history.value.length === 0) return false

    const rows = history.value.map(
      (h) =>
        `| ${h.timestamp} | ${h.mode.toUpperCase()} | ${h.itemCount} | ${h.mountMs} ms | ${h.patchAvgMs} ms (${h.patchFps} fps) | ${h.unmountMs} ms | ${h.heapMb ? `${h.heapMb} MB` : 'N/A'} |`,
    )

    const markdown = [
      '### 纸间 · Vue 3.6 Vapor Mode 基准跑分报告',
      '',
      '| 时间 | 模式 | 节点数 | 初始挂载 | 响应式补丁 (帧率) | 节点卸载 | JS 堆内存 |',
      '| :--- | :--- | :--- | :--- | :--- | :--- | :--- |',
      ...rows,
      '',
      '> 硬件环境测试基准：纸间 /vapor-canary 基准沙盒',
    ].join('\n')

    try {
      await navigator.clipboard.writeText(markdown)
      return true
    } catch {
      return false
    }
  }

  const hasResults = computed(() => history.value.length > 0)

  return {
    mode,
    itemCount,
    items,
    isRunning,
    isPatching,
    mountDuration,
    patchAvgDuration,
    patchFps,
    unmountDuration,
    heapUsedMb,
    history,
    hasResults,
    runMountTest,
    runPatchTest,
    runUnmountTest,
    runFullSuite,
    copyReport,
  }
}

/**
 * canvasProbe.ts — WICG HTML-in-Canvas 与现代图形能力探测工具
 *
 * 遵循 WICG HTML-in-Canvas 规范草案（Chromium 155+ chrome://flags/#canvas-draw-element）。
 * 仅用于未来图文合成、海报导出及 AVG 互动游戏实验室探测，严禁用于基础文档流长列表卡片。
 */

/**
 * 探测当前浏览器是否原生支持 Canvas 2D drawElementImage
 */
export function isDrawElementSupported(): boolean {
  if (typeof window === 'undefined') return false
  const ctxProto = window.CanvasRenderingContext2D?.prototype
  return Boolean(ctxProto && 'drawElementImage' in ctxProto)
}

/**
 * 探测当前浏览器是否支持 <canvas layoutsubtree> 原生属性
 */
export function isLayoutSubtreeSupported(): boolean {
  if (typeof document === 'undefined') return false
  const canvas = document.createElement('canvas')
  return 'layoutSubtree' in canvas || 'layoutsubtree' in canvas
}

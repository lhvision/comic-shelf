import { readonly, ref } from 'vue'

export interface Toast {
  id: number
  text: string
  tone: 'info' | 'error' | 'success'
}

const toasts = ref<Toast[]>([])
let nextId = 1
const activeTimers = new Map<number, number>()

/**
 * 在端侧弹出一条轻量提示。
 *
 * 防抖与去重守卫：
 * 若当前已存在同文案且同音调（text + tone）的未消除提示，
 * 刷新其自动消除倒计时并直接复用现有卡片，杜绝响应式监听与子组件并发引发的叠词弹窗。
 */
function push(text: string, tone: 'info' | 'error' | 'success' = 'info'): number {
  const trimmed = text.trim()
  if (!trimmed) return 0

  const existing = toasts.value.find((t) => t.text === trimmed && t.tone === tone)
  if (existing) {
    const prevTimer = activeTimers.get(existing.id)
    if (prevTimer) clearTimeout(prevTimer)
    const newTimer = window.setTimeout(() => {
      dismiss(existing.id)
    }, 4200)
    activeTimers.set(existing.id, newTimer)
    return existing.id
  }

  const id = nextId++
  toasts.value.push({ id, text: trimmed, tone })
  const timer = window.setTimeout(() => {
    dismiss(id)
  }, 4200)
  activeTimers.set(id, timer)
  return id
}

function dismiss(id: number) {
  const timer = activeTimers.get(id)
  if (timer) {
    clearTimeout(timer)
    activeTimers.delete(id)
  }
  const index = toasts.value.findIndex((toast) => toast.id === id)
  if (index !== -1) toasts.value.splice(index, 1)
}

export function useToast() {
  return {
    toasts: readonly(toasts),
    toast: push,
    dismiss,
  }
}

import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { useToast } from '@/composables/useToast'

describe('useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    const { toasts, dismiss } = useToast()
    // 清理可能残留的 toast
    while (toasts.value.length > 0) {
      const first = toasts.value[0]
      if (first) {
        dismiss(first.id)
      } else {
        break
      }
    }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('能够正常压入 Toast 并自适应定时销毁', () => {
    const { toasts, toast } = useToast()
    const id = toast('操作成功', 'success')
    expect(toasts.value).toHaveLength(1)
    expect(toasts.value[0]).toEqual({
      id,
      text: '操作成功',
      tone: 'success',
    })

    // 推进 4200ms
    vi.advanceTimersByTime(4200)
    expect(toasts.value).toHaveLength(0)
  })

  it('同文案同音调短时内压入自动去重并刷新倒计时', () => {
    const { toasts, toast } = useToast()

    const id1 = toast('受权限保护的画卷', 'error')
    expect(toasts.value).toHaveLength(1)

    // 推进 2000ms（尚未过期）
    vi.advanceTimersByTime(2000)

    // 再次压入完全一致的错误提示
    const id2 = toast('受权限保护的画卷', 'error')
    expect(id2).toBe(id1)
    expect(toasts.value).toHaveLength(1)

    // 再推进 2500ms（总计 4500ms，按初始定时器本应销毁，但因刷新了 4200ms 倒计时仍然存活）
    vi.advanceTimersByTime(2500)
    expect(toasts.value).toHaveLength(1)

    // 再推进 1800ms（自刷新起满 4200ms），正常销毁
    vi.advanceTimersByTime(1800)
    expect(toasts.value).toHaveLength(0)
  })

  it('不同文案或不同音调不被去重阻断', () => {
    const { toasts, toast } = useToast()

    toast('错误 A', 'error')
    toast('错误 B', 'error')
    toast('错误 A', 'info')

    expect(toasts.value).toHaveLength(3)
  })

  it('忽略纯空白字符串', () => {
    const { toasts, toast } = useToast()
    const id = toast('   ', 'error')
    expect(id).toBe(0)
    expect(toasts.value).toHaveLength(0)
  })
})

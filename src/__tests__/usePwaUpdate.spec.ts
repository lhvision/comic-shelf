import { describe, it, expect } from 'vite-plus/test'
import { usePwaUpdate } from '@/composables/usePwaUpdate'
import { useSystemEvents } from '@/composables/useSystemEvents'

describe('usePwaUpdate & useSystemEvents composables', () => {
  it('manages PWA refresh prompt state properly', () => {
    const { needRefresh, hasDismissedPrompt, showPrompt, dismissPrompt } = usePwaUpdate()

    needRefresh.value = false
    hasDismissedPrompt.value = false
    expect(showPrompt.value).toBe(false)

    needRefresh.value = true
    expect(showPrompt.value).toBe(true)

    dismissPrompt()
    expect(hasDismissedPrompt.value).toBe(true)
    expect(showPrompt.value).toBe(false)
  })

  it('manages SSE system events state properly', () => {
    const { isConnected, isSleeping } = useSystemEvents()
    expect(isConnected.value).toBe(false)
    expect(isSleeping.value).toBe(false)
  })
})

import { describe, it, expect, vi } from 'vite-plus/test'
import { usePwaInstall } from '@/composables/usePwaInstall'

describe('usePwaInstall composable', () => {
  it('provides reactive PWA install states and platform detection', () => {
    const { canInstall, isStandalone, isIos, showIosGuide, installApp } = usePwaInstall()

    expect(typeof canInstall.value).toBe('boolean')
    expect(typeof isStandalone.value).toBe('boolean')
    expect(typeof isIos.value).toBe('boolean')
    expect(typeof showIosGuide.value).toBe('boolean')
    expect(typeof installApp).toBe('function')
  })

  it('handles installApp safely when no prompt is available', async () => {
    const { installApp } = usePwaInstall()
    const result = await installApp()
    expect(result).toBe(false)
  })

  it('triggers prompt when deferredPrompt exists', async () => {
    const { canInstall, installApp } = usePwaInstall()
    const promptMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
    const fakeEvent = {
      preventDefault: vi.fn<() => void>(),
      prompt: promptMock,
      userChoice: Promise.resolve({ outcome: 'accepted', platform: 'web' }),
      platforms: ['web'],
    }

    // Simulate beforeinstallprompt event
    window.dispatchEvent(Object.assign(new Event('beforeinstallprompt'), fakeEvent))

    expect(canInstall.value).toBe(true)
    const installed = await installApp()
    expect(promptMock).toHaveBeenCalled()
    expect(installed).toBe(true)
    expect(canInstall.value).toBe(false)
  })
})

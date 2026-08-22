import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { useCoverTransition } from '@/composables/useCoverTransition'

describe('useCoverTransition', () => {
  beforeEach(() => {
    const { clearActiveCover } = useCoverTransition()
    clearActiveCover()
  })

  it('tracks active cover state accurately', () => {
    const { setActiveCover, isCoverActive, clearActiveCover } = useCoverTransition()

    expect(isCoverActive('jm', '523607')).toBe(false)

    setActiveCover('jm', '523607')
    expect(isCoverActive('jm', '523607')).toBe(true)
    expect(isCoverActive('jm', '123456')).toBe(false)

    clearActiveCover()
    expect(isCoverActive('jm', '523607')).toBe(false)
  })
})

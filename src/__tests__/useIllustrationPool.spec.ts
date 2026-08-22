import { describe, it, expect } from 'vite-plus/test'
import { useIllustrationPool, DEFAULT_ILLUSTRATIONS } from '@/composables/useIllustrationPool'

describe('useIllustrationPool', () => {
  it('returns default illustrations and valid count', () => {
    const { illustrations, count } = useIllustrationPool()
    expect(illustrations.length).toBeGreaterThanOrEqual(4)
    expect(count).toBe(illustrations.length)
    expect(illustrations).toEqual(DEFAULT_ILLUSTRATIONS)
  })

  it('getRandomIllustration returns a valid url from the pool', () => {
    const { illustrations, getRandomIllustration } = useIllustrationPool()
    const random = getRandomIllustration()
    expect(illustrations).toContain(random)
  })

  it('getIllustration resolves 1-based index correctly', () => {
    const { getIllustration } = useIllustrationPool()
    expect(getIllustration(1)).toBe('/loading-1.webp')
    expect(getIllustration(2)).toBe('/loading-2.webp')
    expect(getIllustration(3)).toBe('/loading-3.webp')
    expect(getIllustration(4)).toBe('/loading-4.webp')
  })

  it('getIllustration handles custom path string', () => {
    const { getIllustration } = useIllustrationPool()
    expect(getIllustration('/custom-loading.webp')).toBe('/custom-loading.webp')
    expect(getIllustration('custom-loading.webp')).toBe('/custom-loading.webp')
  })
})

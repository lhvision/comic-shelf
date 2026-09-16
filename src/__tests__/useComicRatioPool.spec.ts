import { describe, it, expect } from 'vite-plus/test'
import { ref, nextTick } from 'vue'
import { useComicRatioPool } from '@/composables/useComicRatioPool'

describe('useComicRatioPool - Cross-View Aspect Ratio Sharing Pool', () => {
  it('shares recorded page ratios across different component instances', () => {
    const comicKey = ref('jm/123456')

    // Instance 1: Primary Viewport
    const viewportPool = useComicRatioPool(comicKey)
    // Instance 2: Filmstrip Scrubber
    const filmstripPool = useComicRatioPool(comicKey)
    // Instance 3: Hover Preview Popover
    const popoverPool = useComicRatioPool(comicKey)

    // Initially all are undefined
    expect(viewportPool.getPageRatio(1)).toBeNull()
    expect(filmstripPool.getPageRatio(1)).toBeNull()
    expect(popoverPool.getPageRatio(1)).toBeNull()

    // Viewport decodes page 1 with ratio '800 / 1200'
    viewportPool.setPageRatio(1, '800 / 1200')

    // Both Filmstrip and Popover immediately see the ratio and default ratio
    expect(filmstripPool.getPageRatio(1)).toBe('800 / 1200')
    expect(popoverPool.getPageRatio(1)).toBe('800 / 1200')
    expect(filmstripPool.defaultComicRatio.value).toBe('800 / 1200')

    // Unrecorded page inherits the default ratio
    expect(filmstripPool.getPageRatio(99)).toBe('800 / 1200')
    expect(popoverPool.getPageStyle(99)).toEqual({
      '--quiescent-ratio': '800 / 1200',
      aspectRatio: '800 / 1200',
    })
  })

  it('isolates different comics and switches cleanly', async () => {
    const comicKey = ref('local/comic-a')
    const pool = useComicRatioPool(comicKey)

    pool.setPageRatio(1, '3 / 4')
    expect(pool.getPageRatio(1)).toBe('3 / 4')

    // Switch to another comic
    comicKey.value = 'local/comic-b'
    await nextTick()

    // New comic starts fresh
    expect(pool.defaultComicRatio.value).toBeNull()
    expect(pool.getPageRatio(1)).toBeNull()

    // Set new ratio for comic B
    pool.setPageRatio(1, '16 / 9')
    expect(pool.getPageRatio(1)).toBe('16 / 9')
  })

  it('enforces true LRU eviction (refreshes accessed comic and evicts least recently used)', () => {
    // Fill 24 entries: comic-1 to comic-24
    for (let i = 1; i <= 24; i++) {
      const p = useComicRatioPool(ref(`lru-comic-${i}`))
      p.setPageRatio(1, `1 / ${i}`)
    }

    // Access comic-1 again to refresh its LRU position
    const p1 = useComicRatioPool(ref('lru-comic-1'))
    expect(p1.getPageRatio(1)).toBe('1 / 1')

    // Add comic-25 (exceeding MAX_POOL_ENTRIES=24)
    const p25 = useComicRatioPool(ref('lru-comic-25'))
    p25.setPageRatio(1, '1 / 25')

    // comic-1 should STILL be cached because it was recently accessed
    expect(p1.getPageRatio(1)).toBe('1 / 1')

    // comic-2 was the least recently used, so it should have been evicted
    const p2 = useComicRatioPool(ref('lru-comic-2'))
    expect(p2.getPageRatio(1)).toBeNull()
  })
})

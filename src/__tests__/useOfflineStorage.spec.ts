import { describe, it, expect } from 'vite-plus/test'
import { formatBytes, useOfflineStorage } from '@/composables/useOfflineStorage'

describe('useOfflineStorage composable', () => {
  it('formats bytes into human readable representations', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(-10)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1024 * 1024 * 3.4)).toBe('3.4 MB')
    expect(formatBytes(1024 * 1024 * 1024 * 4.5)).toBe('4.5 GB')
  })

  it('provides reactive storage state and estimate properties', () => {
    const storage = useOfflineStorage()
    expect(typeof storage.usage.value).toBe('number')
    expect(typeof storage.quota.value).toBe('number')
    expect(storage.clearing.value).toBe(false)
    expect(typeof storage.badgeText.value).toBe('string')
  })

  it('computes correct percentage and formatted values', () => {
    const storage = useOfflineStorage()
    storage.quota.value = 1000
    storage.usage.value = 250
    expect(storage.percentage.value).toBe(25)
    expect(storage.usageFormatted.value).toBe('250 B')
    expect(storage.quotaFormatted.value).toBe('1000 B')
  })

  it('handles empty quota without NaN or infinity', () => {
    const storage = useOfflineStorage()
    storage.quota.value = 0
    storage.usage.value = 100
    expect(storage.percentage.value).toBe(0)
  })

  it('provides unambiguous device badge text and handles environment status', () => {
    const storage = useOfflineStorage()
    storage.usage.value = 0
    expect(storage.badgeText.value).toBe('离线存储')

    storage.usage.value = 1024 * 1024 * 8.5
    expect(storage.badgeText.value).toBe('离线存储')

    // In jsdom environment without serviceWorker/caches, it correctly detects unsupported
    expect(storage.environmentStatus.value).toBe('unsupported')
  })

  it('provides reactive coreAssetBytes and accurate formatted string', () => {
    const storage = useOfflineStorage()
    storage.coreAssetBytes.value = 950 * 1024
    expect(storage.coreAssetBytesFormatted.value).toBe('950 KB')

    storage.coreAssetBytes.value = 1024 * 1024 * 1.2
    expect(storage.coreAssetBytesFormatted.value).toBe('1.2 MB')
  })

  it('accurately attributes physical storage to manga images without polluting core assets', async () => {
    const storage = useOfflineStorage()

    // 模拟真实浏览器 CacheStorage 与 estimate
    const mockPrecache = {
      keys: async () => [new Request('http://localhost/assets/app.js')],
      match: async () => ({
        headers: new Headers({ 'content-length': String(1024 * 1024) }), // 1 MB
      }),
    }

    const mockMangaCache = {
      keys: async () =>
        Array.from({ length: 497 }, (_, i) => new Request(`http://localhost/api/pages/${i}`)),
      match: async () => ({
        headers: new Headers({ 'content-length': String(200 * 1024) }),
      }),
    }

    const originalStorageDescriptor = Object.getOwnPropertyDescriptor(navigator, 'storage')
    const originalCaches = globalThis.caches

    try {
      Object.defineProperty(navigator, 'storage', {
        value: {
          estimate: () =>
            Promise.resolve({
              quota: 10 * 1024 * 1024 * 1024,
              usage: 87 * 1024 * 1024, // 87 MB
              usageDetails: {
                caches: 86 * 1024 * 1024, // 86 MB CacheStorage
              },
            }),
        },
        configurable: true,
      })

      const cachesMap = new Map<string, unknown>([
        ['workbox-precache-v2-http://localhost/', mockPrecache],
        ['manga-images-cache', mockMangaCache],
      ])

      Object.defineProperty(globalThis, 'caches', {
        value: {
          keys: () => Promise.resolve(Array.from(cachesMap.keys())),
          open: (name: string) => Promise.resolve(cachesMap.get(name)),
          delete: (name: string) => Promise.resolve(cachesMap.delete(name)),
        },
        configurable: true,
      })

      await storage.refreshEstimate()

      // 核心资产必须独立且真实反映 Precache (~1 MB)，绝不被画页反向污染膨胀到 56 MB
      expect(storage.coreAssetBytes.value).toBe(1024 * 1024)
      expect(storage.coreAssetBytesFormatted.value).toBe('1.0 MB')

      // 漫画画页必须正确统计为 497 张，且真实占用对齐为 86 MB - 1 MB = 85 MB (或根据 usageDetails.caches 对齐)
      expect(storage.mangaImageCount.value).toBe(497)
      expect(storage.mangaImageBytes.value).toBe(85 * 1024 * 1024)
      expect(storage.mangaImageBytesFormatted.value).toBe('85 MB')
    } finally {
      if (originalStorageDescriptor) {
        Object.defineProperty(navigator, 'storage', originalStorageDescriptor)
      }
      if (originalCaches) {
        Object.defineProperty(globalThis, 'caches', {
          value: originalCaches,
          configurable: true,
        })
      }
    }
  })

  it('prevents re-entrant clearing operations when clearing is active', async () => {
    const storage = useOfflineStorage()
    storage.clearing.value = true
    const clearResult = await storage.clearImageCache()
    expect(clearResult).toEqual({ freedBytes: 0, freedCount: 0 })

    const resetResult = await storage.resetAllStorage()
    expect(resetResult).toBe(0)
    storage.clearing.value = false
  })
})

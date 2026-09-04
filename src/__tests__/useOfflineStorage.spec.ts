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
    expect(storage.badgeText.value).toBe('设备离线')

    storage.usage.value = 1024 * 1024 * 8.5
    expect(storage.badgeText.value).toBe('设备离线')

    // In jsdom environment without serviceWorker/caches, it correctly detects unsupported
    expect(storage.environmentStatus.value).toBe('unsupported')
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

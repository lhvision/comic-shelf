import { computed, ref } from 'vue'
import { createGlobalState } from '@vueuse/core'
import { withResolvers } from '@/utils/promise'

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), units.length - 1)
  const val = bytes / Math.pow(k, i)
  return `${val < 10 && i > 0 ? val.toFixed(1) : Math.round(val)} ${units[i]}`
}

export const MANGA_IMAGE_MAX_BUDGET = 3000

export const useOfflineStorage = createGlobalState(() => {
  const usage = ref(0)
  const quota = ref(0)
  const mangaImageCount = ref(0)
  const mangaImageBytes = ref(0)
  const clearing = ref(false)

  const isSupported = computed(() => {
    return (
      typeof navigator !== 'undefined' &&
      'storage' in navigator &&
      typeof navigator.storage?.estimate === 'function'
    )
  })

  // 物理磁盘配额百分比
  const percentage = computed(() => {
    if (!quota.value || quota.value <= 0) return 0
    return Math.min(100, Math.max(0, (usage.value / quota.value) * 100))
  })

  // 漫画画页离线预算百分比（相对于 3,000 张上限）
  const budgetPercentage = computed(() => {
    if (mangaImageCount.value <= 0) return 0
    return Math.min(100, Math.max(0, (mangaImageCount.value / MANGA_IMAGE_MAX_BUDGET) * 100))
  })

  const usageFormatted = computed(() => formatBytes(usage.value))
  const quotaFormatted = computed(() => formatBytes(quota.value))

  const coreAssetBytes = computed(() => {
    const raw = usage.value - mangaImageBytes.value
    return Math.max(0, raw)
  })

  const coreAssetBytesFormatted = computed(() => formatBytes(coreAssetBytes.value))
  const mangaImageBytesFormatted = computed(() => formatBytes(mangaImageBytes.value))

  const isSecureContext = computed(() => {
    if (typeof window === 'undefined') return true
    return window.isSecureContext !== false
  })

  const environmentStatus = computed<'ready' | 'insecure_http' | 'unsupported'>(() => {
    if (typeof window === 'undefined') return 'ready'
    if (window.isSecureContext === false) return 'insecure_http'
    if (!('serviceWorker' in navigator) || typeof caches === 'undefined') return 'unsupported'
    return 'ready'
  })

  const badgeText = computed(() => {
    return '离线存储'
  })

  async function refreshEstimate(): Promise<void> {
    if (typeof window === 'undefined') return
    try {
      if (isSupported.value) {
        const estimate = await navigator.storage.estimate()
        usage.value = estimate.usage ?? 0
        quota.value = estimate.quota ?? 0

        // 细分探测 CacheStorage 中的漫画图片缓存
        if (typeof caches !== 'undefined') {
          const cacheKeys = await caches.keys()
          const imageCacheNames = cacheKeys.filter(
            (k) => k.includes('manga-images') || k.includes('images'),
          )

          let count = 0
          const cacheEntries: { cache: Cache; requests: readonly Request[] }[] = []

          for (const name of imageCacheNames) {
            try {
              const cache = await caches.open(name)
              const requests = await cache.keys()
              count += requests.length
              cacheEntries.push({ cache, requests })
            } catch {
              // 忽略单个缓存打开异常
            }
          }
          // 立即更新数量，界面第一时间呈现
          mangaImageCount.value = count

          if (count === 0) {
            mangaImageBytes.value = 0
          } else {
            // 限制并发与样本量：若 <= 50 全量并行；若 > 50 抽样前 40 张估算平均单图大小线性推算
            let calculatedBytes = 0
            const SAMPLE_LIMIT = 40
            const sampleTasks: Promise<number>[] = []
            let sampledCount = 0

            outer: for (const { cache, requests } of cacheEntries) {
              for (const req of requests) {
                if (sampledCount >= SAMPLE_LIMIT && count > 50) break outer
                sampledCount++
                sampleTasks.push(
                  cache
                    .match(req)
                    .then((res) => {
                      if (!res) return 0
                      const len = res.headers.get('content-length')
                      return len ? parseInt(len, 10) || 0 : 0
                    })
                    .catch(() => 0),
                )
              }
            }

            const sampledSizes = await Promise.all(sampleTasks)
            const validSizes = sampledSizes.filter((s) => s > 0)
            if (validSizes.length > 0) {
              const sumSampled = validSizes.reduce((acc, curr) => acc + curr, 0)
              if (count <= 50 || count === validSizes.length) {
                calculatedBytes = sumSampled
              } else {
                const avgBytes = sumSampled / validSizes.length
                calculatedBytes = Math.round(avgBytes * count)
              }
            }

            if (calculatedBytes > 0) {
              mangaImageBytes.value = calculatedBytes
            } else {
              // 回退估算：优先从 usageDetails.caches 扣除核心外壳（~1.5MB），或按每张约 120KB 兜底
              const cachesTotal = (estimate as unknown as { usageDetails?: { caches?: number } })
                .usageDetails?.caches
              if (typeof cachesTotal === 'number' && cachesTotal > 0) {
                mangaImageBytes.value = Math.max(count * 80 * 1024, cachesTotal - 1.5 * 1024 * 1024)
              } else {
                mangaImageBytes.value = count * 120 * 1024
              }
            }
          }
        }
      }
    } catch {
      // 降级守卫
    }
  }

  /**
   * 深度清空指定 IndexedDB 内部的数据表记录并尝试删除数据库，
   * 避免因 Service Worker 长连接未释放导致 deleteDatabase 触发 blocked 挂起。
   * 增加 1.5s 兜底超时与 onabort 容错，防止 IDB 事务异常挂死。
   */
  async function clearIndexedDbRecords(dbName: string, targetStoreName?: string): Promise<void> {
    if (typeof indexedDB === 'undefined') return
    const { promise, resolve } = withResolvers<void>()

    // 1.5s 兜底定时器，防止 IDB 锁死阻塞整个重置流程
    const timer = setTimeout(resolve, 1500)

    try {
      const openReq = indexedDB.open(dbName)
      openReq.onsuccess = () => {
        const db = openReq.result
        const allStores = Array.from(db.objectStoreNames)
        const storesToClear = targetStoreName
          ? allStores.filter((name) => name === targetStoreName || name.includes(targetStoreName))
          : allStores

        if (storesToClear.length > 0) {
          try {
            const tx = db.transaction(storesToClear, 'readwrite')
            for (const name of storesToClear) {
              tx.objectStore(name).clear()
            }
            const done = () => {
              clearTimeout(timer)
              db.close()
              resolve()
            }
            tx.oncomplete = done
            tx.onerror = done
            tx.onabort = done
          } catch {
            clearTimeout(timer)
            db.close()
            resolve()
          }
        } else {
          clearTimeout(timer)
          db.close()
          resolve()
        }
      }
      openReq.onerror = () => {
        clearTimeout(timer)
        resolve()
      }
      openReq.onblocked = () => {
        clearTimeout(timer)
        resolve()
      }
    } catch {
      clearTimeout(timer)
      resolve()
    }

    await promise

    // 仅在全量清空（未指定 targetStoreName）时才执行彻底删除库
    if (!targetStoreName) {
      try {
        indexedDB.deleteDatabase(dbName)
      } catch {
        // 降级容错
      }
    }
  }

  async function clearImageCache(): Promise<{ freedBytes: number; freedCount: number }> {
    if (typeof caches === 'undefined' || clearing.value) return { freedBytes: 0, freedCount: 0 }
    clearing.value = true
    const prevBytes = mangaImageBytes.value
    const prevCount = mangaImageCount.value

    try {
      const keys = await caches.keys()
      const imageCaches = keys.filter((k) => k.includes('manga-images') || k.includes('images'))

      for (const name of imageCaches) {
        await caches.delete(name)
      }

      // 立即重置前端内存状态，防止异步延迟出现视觉残留
      mangaImageCount.value = 0
      mangaImageBytes.value = 0

      // 仅清理与 manga-images 相关的 IndexedDB objectStore，避免抹除插画池等其他缓存的生命周期元数据
      if (typeof indexedDB !== 'undefined' && typeof indexedDB.databases === 'function') {
        try {
          const dbs = await indexedDB.databases()
          for (const db of dbs) {
            if (db.name && db.name.includes('manga')) {
              await clearIndexedDbRecords(db.name)
            } else if (db.name && db.name.includes('workbox')) {
              await clearIndexedDbRecords(db.name, 'manga-images')
            }
          }
        } catch {
          // ignore
        }
      } else {
        await clearIndexedDbRecords('workbox-expiration', 'manga-images')
      }

      await refreshEstimate()

      const freedBytes = prevBytes || prevCount * 120 * 1024
      return { freedBytes, freedCount: prevCount }
    } finally {
      clearing.value = false
    }
  }

  async function resetAllStorage(): Promise<number> {
    if (typeof window === 'undefined' || clearing.value) return 0
    clearing.value = true
    const prevUsage = usage.value

    try {
      if (typeof caches !== 'undefined') {
        const keys = await caches.keys()
        for (const name of keys) {
          await caches.delete(name)
        }
      }

      if ('serviceWorker' in navigator) {
        const registrations = await navigator.serviceWorker.getRegistrations()
        for (const reg of registrations) {
          await reg.unregister()
        }
      }

      // 清理全部 IndexedDB 缓存元数据
      if (typeof indexedDB !== 'undefined' && typeof indexedDB.databases === 'function') {
        try {
          const dbs = await indexedDB.databases()
          for (const db of dbs) {
            if (db.name && (db.name.includes('workbox') || db.name.includes('manga'))) {
              await clearIndexedDbRecords(db.name)
            }
          }
        } catch {
          // ignore
        }
      } else {
        await clearIndexedDbRecords('workbox-expiration')
      }

      mangaImageCount.value = 0
      mangaImageBytes.value = 0
      usage.value = 0

      await refreshEstimate()
      return prevUsage
    } finally {
      clearing.value = false
    }
  }

  return {
    usage,
    quota,
    percentage,
    budgetPercentage,
    mangaImageCount,
    mangaImageBytes,
    usageFormatted,
    quotaFormatted,
    mangaImageBytesFormatted,
    coreAssetBytesFormatted,
    badgeText,
    isSecureContext,
    environmentStatus,
    clearing,
    refreshEstimate,
    clearImageCache,
    resetAllStorage,
  }
})

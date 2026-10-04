import { computed, ref } from 'vue'
import { createGlobalState } from '@vueuse/core'
import { withResolvers } from '@/utils/promise'
import { clearAllMetadataDb } from '@/utils/offlineDb'
import { formatBytes } from '@/utils/format'
import { clamp, sumPrecise } from '@/utils/math'

export const MANGA_COVER_MAX_BUDGET = 1000

export const useOfflineStorage = createGlobalState(() => {
  const usage = ref(0)
  const quota = ref(0)
  const mangaCoverCount = ref(0)
  const mangaImageBytes = ref(0)
  const clearing = ref(false)
  let estimating = false

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
    return clamp((usage.value / quota.value) * 100, 0, 100)
  })

  // 书库封面离线预算百分比（相对于 1,000 张上限）
  const budgetPercentage = computed(() => {
    if (mangaCoverCount.value <= 0) return 0
    return clamp((mangaCoverCount.value / MANGA_COVER_MAX_BUDGET) * 100, 0, 100)
  })

  const usageFormatted = computed(() => formatBytes(usage.value))
  const quotaFormatted = computed(() => formatBytes(quota.value))

  const coreAssetBytes = ref(0)
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
    if (estimating) return
    estimating = true
    try {
      if (isSupported.value) {
        const estimate = await navigator.storage.estimate()
        usage.value = estimate.usage ?? 0
        quota.value = estimate.quota ?? 0

        // 细分探测 CacheStorage 中的核心资产预缓存与书库封面缓存
        if (typeof caches !== 'undefined') {
          const cacheKeys = await caches.keys()

          // 1. 核心资产预缓存 (Workbox Precache) 独立直接度量（App 外壳 · 脚本 · 字体 · 基础图标）
          const precacheKeys = cacheKeys.filter((k) => k.includes('precache'))
          let precacheBytes = 0
          for (const name of precacheKeys) {
            try {
              const cache = await caches.open(name)
              const requests = await cache.keys()
              const sizeTasks = requests.map((req) =>
                cache
                  .match(req)
                  .then((res) => {
                    if (!res) return 0
                    const len = res.headers.get('content-length')
                    return len ? parseInt(len, 10) || 0 : 0
                  })
                  .catch(() => 0),
              )
              const sizes = await Promise.all(sizeTasks)
              precacheBytes += sumPrecise(sizes)
            } catch {
              // 忽略单个缓存打开异常
            }
          }

          // 兜底：若存在 Precache 桶但 headers 无 content-length（如 chunked/开发代理），使用构建期典型基线 ~950 KiB
          if (precacheKeys.length > 0 && precacheBytes === 0) {
            precacheBytes = 950 * 1024
          }
          coreAssetBytes.value = precacheBytes

          // 2. 存量旧正文画页缓存 (manga-images-cache) 静默自愈清理（释放数个 GB 孤岛数据）
          if (cacheKeys.includes('manga-images-cache')) {
            try {
              await caches.delete('manga-images-cache')
            } catch {
              // 忽略删除异常
            }
          }

          // 3. 书库封面与章节封面缓存统计 (manga-images-covers-cache)
          const coverCacheNames = cacheKeys.filter(
            (k) => k.includes('cover') && !k.includes('precache'),
          )

          let coverCount = 0
          for (const name of coverCacheNames) {
            try {
              const cache = await caches.open(name)
              const requests = await cache.keys()
              coverCount += requests.length
            } catch {
              // 忽略单个缓存打开异常
            }
          }

          mangaCoverCount.value = coverCount

          // 4. 计算封面物理真实占用
          if (coverCount === 0) {
            mangaImageBytes.value = 0
          } else {
            const usageDetails = (estimate as unknown as { usageDetails?: { caches?: number } })
              ?.usageDetails
            const cachesTotal = usageDetails?.caches

            if (typeof cachesTotal === 'number' && cachesTotal > 0) {
              mangaImageBytes.value = Math.max(
                coverCount * 30 * 1024,
                cachesTotal - coreAssetBytes.value,
              )
            } else if (usage.value > coreAssetBytes.value) {
              mangaImageBytes.value = Math.max(
                coverCount * 30 * 1024,
                usage.value - coreAssetBytes.value,
              )
            } else {
              mangaImageBytes.value = coverCount * 45 * 1024
            }
          }
        }
      }
    } catch {
      // 降级守卫
    } finally {
      estimating = false
    }
  }

  /**
   * 深度清空指定 IndexedDB 内部的数据表记录并尝试删除数据库，
   * 避免因 Service Worker 长连接未释放导致 deleteDatabase 触发 blocked 挂起。
   * 增加 1.5s 兜底超时与 onabort 容错，防止 IDB 事务异常挂死。
   */
  async function clearIndexedDbRecords(dbName: string): Promise<void> {
    if (typeof indexedDB === 'undefined') return
    const { promise, resolve } = withResolvers<void>()

    // 1.5s 兜底定时器，防止 IDB 锁死阻塞整个重置流程
    const timer = setTimeout(resolve, 1500)

    try {
      const openReq = indexedDB.open(dbName)
      openReq.onsuccess = () => {
        const db = openReq.result
        const storesToClear = Array.from(db.objectStoreNames)

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

    try {
      indexedDB.deleteDatabase(dbName)
    } catch {
      // 降级容错
    }
  }

  async function clearImageCache(): Promise<{ freedBytes: number; freedCount: number }> {
    if (typeof caches === 'undefined' || clearing.value) return { freedBytes: 0, freedCount: 0 }
    clearing.value = true
    const prevBytes = mangaImageBytes.value
    const prevCount = mangaCoverCount.value

    try {
      const keys = await caches.keys()
      const imageCaches = keys.filter(
        (k) =>
          k.includes('manga-images') ||
          k.includes('images') ||
          k.includes('illustration') ||
          k.includes('illustrations'),
      )

      for (const name of imageCaches) {
        await caches.delete(name)
      }

      // 立即重置前端内存状态，防止异步延迟出现视觉残留
      mangaCoverCount.value = 0
      mangaImageBytes.value = 0

      // 清理与漫画画页及 Workbox 过期索引相关的 IndexedDB 记录，保护用户书架元数据
      if (typeof indexedDB !== 'undefined' && typeof indexedDB.databases === 'function') {
        try {
          const dbs = await indexedDB.databases()
          for (const db of dbs) {
            if (
              db.name &&
              (db.name.includes('manga') ||
                db.name.includes('illustration') ||
                db.name.includes('workbox'))
            ) {
              await clearIndexedDbRecords(db.name)
            }
          }
        } catch {
          // ignore
        }
      } else {
        await clearIndexedDbRecords('workbox-expiration')
      }

      await refreshEstimate()

      const freedBytes = prevBytes || prevCount * 45 * 1024
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
            if (
              db.name &&
              (db.name.includes('workbox') ||
                db.name.includes('manga') ||
                db.name.includes('illustration'))
            ) {
              await clearIndexedDbRecords(db.name)
            }
          }
        } catch {
          // ignore
        }
      } else {
        await clearIndexedDbRecords('workbox-expiration')
      }

      await clearAllMetadataDb()

      mangaCoverCount.value = 0
      mangaImageBytes.value = 0
      coreAssetBytes.value = 0
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
    mangaCoverCount,
    mangaImageBytes,
    coreAssetBytes,
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

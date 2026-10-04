import { computed, ref } from 'vue'
import { createGlobalState } from '@vueuse/core'
import { withResolvers } from '@/utils/promise'
import { clearAllMetadataDb } from '@/utils/offlineDb'
import { formatBytes } from '@/utils/format'
import { clamp, sumPrecise } from '@/utils/math'

export const MANGA_PAGE_MAX_BUDGET = 3000
export const MANGA_COVER_MAX_BUDGET = 1000
export const MANGA_IMAGE_MAX_BUDGET = 4000

/**
 * 对超出预算上限的 Cache 桶执行轻量 FIFO 头部自愈修剪
 *
 * @param cache 目标 CacheStorage 实例
 * @param requests 当前桶内所有已缓存请求数组
 * @param maxAllowed 允许保留的最大条目上限
 * @returns 修剪对齐后的条目数量
 */
async function trimExcessCacheEntries(
  cache: Cache,
  requests: readonly Request[],
  maxAllowed: number,
): Promise<number> {
  const excess = requests.length - maxAllowed
  if (excess <= 0) return requests.length

  const toDelete = requests.slice(0, excess)
  let deletedCount = 0

  // 并发异步删除超出配额的头部陈旧条目，直接释放物理磁盘
  await Promise.all(
    toDelete.map(async (req) => {
      try {
        if (typeof cache.delete === 'function') {
          const res = await cache.delete(req)
          if (res !== false) deletedCount++
        }
      } catch {
        // 忽略单个条目删除异常
      }
    }),
  )

  return requests.length - deletedCount
}

export const useOfflineStorage = createGlobalState(() => {
  const usage = ref(0)
  const quota = ref(0)
  const mangaImageCount = ref(0)
  const mangaPageCount = ref(0)
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

  // 漫画画页与封面离线总预算百分比（相对于 4,000 张上限：3,000 画页 + 1,000 封面）
  const budgetPercentage = computed(() => {
    if (mangaImageCount.value <= 0) return 0
    return clamp((mangaImageCount.value / MANGA_IMAGE_MAX_BUDGET) * 100, 0, 100)
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

        // 细分探测 CacheStorage 中的核心资产预缓存与漫画图片缓存
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

          // 2. 漫画画页与封面缓存统计及轻量自愈修剪（manga-images & covers）
          const mangaCacheNames = cacheKeys.filter(
            (k) => k.includes('manga-images') || k.includes('images'),
          )

          let pageCount = 0
          let coverCount = 0

          for (const name of mangaCacheNames) {
            try {
              const cache = await caches.open(name)
              const requests = await cache.keys()
              const isCover = name.includes('cover')
              const maxBudget = isCover ? MANGA_COVER_MAX_BUDGET : MANGA_PAGE_MAX_BUDGET
              const trimmedCount = await trimExcessCacheEntries(cache, requests, maxBudget)

              if (isCover) {
                coverCount += trimmedCount
              } else {
                pageCount += trimmedCount
              }
            } catch {
              // 忽略单个缓存打开异常
            }
          }

          const count = pageCount + coverCount
          mangaPageCount.value = pageCount
          mangaCoverCount.value = coverCount
          mangaImageCount.value = count

          // 3. 计算画页物理真实占用（对齐浏览器物理磁盘，消除逆向减法对核心资产的污染）
          if (count === 0) {
            mangaImageBytes.value = 0
          } else {
            const usageDetails = (estimate as unknown as { usageDetails?: { caches?: number } })
              ?.usageDetails
            const cachesTotal = usageDetails?.caches

            if (typeof cachesTotal === 'number' && cachesTotal > 0) {
              // 支持 usageDetails.caches：从物理 CacheStorage 中扣除独立测出的核心资产
              mangaImageBytes.value = Math.max(
                count * 60 * 1024,
                cachesTotal - coreAssetBytes.value,
              )
            } else if (usage.value > coreAssetBytes.value) {
              // 通用支持：扣除核心资产后的真实 Origin 物理占用归属于漫画画页与媒体缓存
              mangaImageBytes.value = Math.max(
                count * 60 * 1024,
                usage.value - coreAssetBytes.value,
              )
            } else {
              // 离线/受限环境兜底：按每张画页均值约 180 KB
              mangaImageBytes.value = count * 180 * 1024
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
    const prevCount = mangaImageCount.value

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
      mangaPageCount.value = 0
      mangaCoverCount.value = 0
      mangaImageCount.value = 0
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

      const freedBytes = prevBytes || prevCount * 180 * 1024
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

      mangaPageCount.value = 0
      mangaCoverCount.value = 0
      mangaImageCount.value = 0
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
    mangaImageCount,
    mangaPageCount,
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

/**
 * @file offlineDb.ts
 * @description 客户端离线元数据 IndexedDB 持久化模块（comic-shelf-meta）。
 *
 * 核心契约：
 * 1. 0 外部依赖，原生包装 IndexedDB 事务操作，零 bundle 体积膨胀；
 * 2. 按用户身份（userId/role）隔离存储书架快照（items, facets, providers）与漫画详情（comic_details）；
 * 3. 漫画详情采用 LRU 自动淘汰（上限 200 本），防止端侧元数据无限膨胀；
 * 4. 离线记账队列（offline_actions）承载翻页进度与喜欢标记，支持网络自愈批量回写；
 * 5. 全面防御 SSR/无私有沙盒环境与事务超时异常。
 */

import type { ComicDetail, LibraryFacetsResponse, LibrarySummary, ProviderInfo } from '@/types'
import { withResolvers } from '@/utils/promise'

const DB_NAME = 'comic-shelf-meta'
const DB_VERSION = 1

const STORE_SHELF = 'shelf_snapshots'
const STORE_DETAILS = 'comic_details'
const STORE_ACTIONS = 'offline_actions'

const MAX_CACHED_DETAILS = 200

export interface ShelfSnapshotData {
  key: string
  items: LibrarySummary[]
  facets: LibraryFacetsResponse | null
  providers: ProviderInfo[]
  timestamp: number
}

export interface CachedComicDetailRecord {
  key: string
  source: string
  sourceId: string
  detail: ComicDetail
  timestamp: number
}

export type OfflineActionType = 'reading_progress' | 'favorite'

export interface OfflineActionRecord {
  id?: number
  userId?: string
  type: OfflineActionType
  payload: Record<string, unknown>
  timestamp: number
}

let dbInstance: IDBDatabase | null = null
let dbOpeningPromise: Promise<IDBDatabase | null> | null = null

export function isIndexedDbSupported(): boolean {
  return typeof window !== 'undefined' && typeof indexedDB !== 'undefined'
}

/**
 * 安全打开并复用 IndexedDB 数据库连接
 */
export async function openOfflineDb(): Promise<IDBDatabase | null> {
  if (!isIndexedDbSupported()) return null
  if (dbInstance) return dbInstance
  if (dbOpeningPromise) return dbOpeningPromise

  const { promise, resolve } = withResolvers<IDBDatabase | null>()
  dbOpeningPromise = promise

  try {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = (event) => {
      const db = request.result
      const oldVersion = event.oldVersion

      if (oldVersion < 1) {
        if (!db.objectStoreNames.contains(STORE_SHELF)) {
          db.createObjectStore(STORE_SHELF, { keyPath: 'key' })
        }
        if (!db.objectStoreNames.contains(STORE_DETAILS)) {
          const detailStore = db.createObjectStore(STORE_DETAILS, { keyPath: 'key' })
          detailStore.createIndex('timestamp', 'timestamp', { unique: false })
        }
        if (!db.objectStoreNames.contains(STORE_ACTIONS)) {
          db.createObjectStore(STORE_ACTIONS, { keyPath: 'id', autoIncrement: true })
        }
      }
    }

    request.onsuccess = () => {
      dbInstance = request.result
      dbInstance.onversionchange = () => {
        dbInstance?.close()
        dbInstance = null
      }
      dbInstance.onclose = () => {
        dbInstance = null
      }
      resolve(dbInstance)
      dbOpeningPromise = null
    }

    request.onerror = () => {
      resolve(null)
      dbOpeningPromise = null
    }

    request.onblocked = () => {
      resolve(null)
      dbOpeningPromise = null
    }
  } catch {
    resolve(null)
    dbOpeningPromise = null
  }

  return promise
}

function getEffectiveUserKey(userId?: string): string {
  return userId && userId.trim() ? userId.trim() : 'default'
}

/* ---------------- 1. 书架快照管理 ---------------- */

/**
 * 保存书架列表、全貌统计与数据源快照至 IndexedDB
 */
export async function saveShelfSnapshot(
  userId: string,
  data: {
    items: LibrarySummary[]
    facets: LibraryFacetsResponse | null
    providers?: ProviderInfo[]
  },
): Promise<void> {
  const db = await openOfflineDb()
  if (!db) return

  const userKey = getEffectiveUserKey(userId)
  const snapshotKey = `shelf_${userKey}`
  const record: ShelfSnapshotData = {
    key: snapshotKey,
    items: data.items,
    facets: data.facets,
    providers: data.providers ?? [],
    timestamp: Date.now(),
  }

  const { promise, resolve } = withResolvers<void>()
  try {
    const tx = db.transaction(STORE_SHELF, 'readwrite')
    const store = tx.objectStore(STORE_SHELF)
    store.put(record)

    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
    tx.onabort = () => resolve()
  } catch {
    resolve()
  }
  return promise
}

/**
 * 获取指定用户的书架离线快照
 */
export async function getShelfSnapshot(userId?: string): Promise<ShelfSnapshotData | null> {
  const db = await openOfflineDb()
  if (!db) return null

  const userKey = getEffectiveUserKey(userId)
  const isGuestUser = userKey.startsWith('guest:')
  const snapshotKey = `shelf_${userKey}`

  const { promise, resolve } = withResolvers<ShelfSnapshotData | null>()
  try {
    const tx = db.transaction(STORE_SHELF, 'readonly')
    const store = tx.objectStore(STORE_SHELF)
    const req = store.get(snapshotKey)

    req.onsuccess = () => {
      const res = req.result as ShelfSnapshotData | undefined
      if (res) {
        if (isGuestUser && Array.isArray(res.items)) {
          resolve({
            ...res,
            items: res.items.filter((item) => !item.hidden_from_guest),
          })
          return
        }
        resolve(res)
        return
      }

      // 访客安全防御：若为访客，严禁跨租户降级回退至馆长快照
      if (isGuestUser) {
        resolve(null)
        return
      }

      // 容错托底：若指定用户键未命中（例如离线初次加载丢失精确 userId 或 default 查无记录），
      // 遍历 STORE_SHELF 中保存的全部快照，回退使用时间戳最新的有效书架快照
      const allReq = store.getAll()
      allReq.onsuccess = () => {
        const all = (allReq.result as ShelfSnapshotData[]) || []
        if (all.length > 0) {
          all.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
          resolve(all[0] || null)
        } else {
          resolve(null)
        }
      }
      allReq.onerror = () => resolve(null)
    }
    req.onerror = () => resolve(null)
    tx.onerror = () => resolve(null)
  } catch {
    resolve(null)
  }
  return promise
}

/* ---------------- 2. 漫画详情缓存（LRU 200） ---------------- */

/**
 * 保存单本漫画详情至 IndexedDB
 */
export async function saveComicDetail(userId: string, detail: ComicDetail): Promise<void> {
  const db = await openOfflineDb()
  if (!db || !detail?.meta?.source || !detail.meta.source_id) return

  const userKey = getEffectiveUserKey(userId)
  const key = `${userKey}/${detail.meta.source}/${detail.meta.source_id}`
  const record: CachedComicDetailRecord = {
    key,
    source: detail.meta.source,
    sourceId: detail.meta.source_id,
    detail,
    timestamp: Date.now(),
  }

  const { promise, resolve } = withResolvers<void>()
  try {
    const tx = db.transaction(STORE_DETAILS, 'readwrite')
    const store = tx.objectStore(STORE_DETAILS)
    store.put(record)

    // LRU 淘汰：若超过最大条目数，删除最久未访问的记录
    const countReq = store.count()
    countReq.onsuccess = () => {
      if (countReq.result > MAX_CACHED_DETAILS) {
        const index = store.index('timestamp')
        const cursorReq = index.openCursor()
        let toDelete = countReq.result - MAX_CACHED_DETAILS
        cursorReq.onsuccess = () => {
          const cursor = cursorReq.result
          if (cursor && toDelete > 0) {
            cursor.delete()
            toDelete--
            cursor.continue()
          }
        }
      }
    }

    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
    tx.onabort = () => resolve()
  } catch {
    resolve()
  }
  return promise
}

/**
 * 从 IndexedDB 获取单本漫画详情
 */
export async function getComicDetail(
  userId: string,
  source: string,
  sourceId: string,
): Promise<ComicDetail | null> {
  const db = await openOfflineDb()
  if (!db || !source || !sourceId) return null

  const userKey = getEffectiveUserKey(userId)
  const isGuestUser = userKey.startsWith('guest:')
  const key = `${userKey}/${source}/${sourceId}`

  const { promise, resolve } = withResolvers<ComicDetail | null>()
  try {
    const tx = db.transaction(STORE_DETAILS, 'readwrite')
    const store = tx.objectStore(STORE_DETAILS)
    const req = store.get(key)

    req.onsuccess = () => {
      const res = req.result as CachedComicDetailRecord | undefined
      if (res?.detail) {
        // 访客安全防御：禁止离线读取对访客隐藏的漫画
        if (isGuestUser && res.detail.meta?.hidden_from_guest) {
          resolve(null)
          return
        }
        // 更新访问时间戳，延长 LRU 寿命
        res.timestamp = Date.now()
        store.put(res)
        resolve(res.detail)
      } else {
        // 访客安全防御：若为访客且未直接命中自有缓存，严禁越权兜底检索馆长或其他用户的全量缓存记录
        if (isGuestUser) {
          resolve(null)
          return
        }
        // 容错降级：若特定 userKey 未命中，检索 STORE_DETAILS 中匹配该漫画源与 ID 的最新有效记录
        const allReq = store.getAll()
        allReq.onsuccess = () => {
          const records = (allReq.result as CachedComicDetailRecord[]) || []
          const match = records
            .filter((r) => r.source === source && r.sourceId === sourceId && r.detail)
            .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))[0]
          if (match?.detail) {
            match.timestamp = Date.now()
            store.put(match)
            resolve(match.detail)
          } else {
            resolve(null)
          }
        }
        allReq.onerror = () => resolve(null)
      }
    }
    req.onerror = () => resolve(null)
    tx.onerror = () => resolve(null)
  } catch {
    resolve(null)
  }
  return promise
}

/**
 * 获取 IndexedDB 中缓存的全部漫画详情（支持按用户键过滤或作为全局离线托底）
 */
export async function getAllCachedComicDetails(userId?: string): Promise<ComicDetail[]> {
  const db = await openOfflineDb()
  if (!db) return []

  const userKey = userId && userId.trim() ? userId.trim() : undefined
  const isGuestUser = userKey ? userKey.startsWith('guest:') : false
  const { promise, resolve } = withResolvers<ComicDetail[]>()
  try {
    const tx = db.transaction(STORE_DETAILS, 'readonly')
    const store = tx.objectStore(STORE_DETAILS)
    const req = store.getAll()

    req.onsuccess = () => {
      const records = (req.result as CachedComicDetailRecord[]) || []
      let matched = userKey ? records.filter((r) => r.key.startsWith(`${userKey}/`)) : records
      // 访客安全防御：若为访客，未匹配到专属记录时不回退至全量库
      if (matched.length === 0 && !isGuestUser) {
        matched = records
      }
      let details = matched.map((r) => r.detail).filter(Boolean)
      if (isGuestUser) {
        details = details.filter((d) => !d.meta?.hidden_from_guest)
      }
      resolve(details)
    }
    req.onerror = () => resolve([])
    tx.onerror = () => resolve([])
  } catch {
    resolve([])
  }
  return promise
}

/**
 * 从 IndexedDB 中删除指定漫画的所有详情缓存（支持按 source + sourceId 精准清理全部用户维度的记录）
 */
export async function deleteCachedComicDetail(source: string, sourceId: string): Promise<void> {
  const db = await openOfflineDb()
  if (!db || !source || !sourceId) return

  const { promise, resolve } = withResolvers<void>()
  try {
    const tx = db.transaction(STORE_DETAILS, 'readwrite')
    const store = tx.objectStore(STORE_DETAILS)
    const req = store.getAll()
    req.onsuccess = () => {
      const records = (req.result as CachedComicDetailRecord[]) || []
      for (const r of records) {
        if (r.source === source && r.sourceId === sourceId) {
          store.delete(r.key)
        }
      }
      resolve()
    }
    req.onerror = () => resolve()
    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
  } catch {
    resolve()
  }
  return promise
}

/**
 * 清理指定漫画在离线队列中尚未回写的所有残留动作（避免重连后向已删除漫画回写脏数据）
 */
export async function removeOfflineActionsForComic(
  source: string,
  sourceId: string,
): Promise<void> {
  const db = await openOfflineDb()
  if (!db || !source || !sourceId) return

  const { promise, resolve } = withResolvers<void>()
  try {
    const tx = db.transaction(STORE_ACTIONS, 'readwrite')
    const store = tx.objectStore(STORE_ACTIONS)
    const req = store.getAll()
    req.onsuccess = () => {
      const records = (req.result as OfflineActionRecord[]) || []
      for (const r of records) {
        const payload = r.payload as Record<string, unknown> | undefined
        if (
          payload &&
          payload.source === source &&
          payload.sourceId === sourceId &&
          r.id !== undefined
        ) {
          store.delete(r.id)
        }
      }
      resolve()
    }
    req.onerror = () => resolve()
    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
  } catch {
    resolve()
  }
  return promise
}

/* ---------------- 3. 离线事务记账队列 ---------------- */

/**
 * 向离线事务队列推入待同步操作
 */
export async function enqueueOfflineAction(action: {
  type: OfflineActionType
  payload: Record<string, unknown>
  userId?: string
}): Promise<number | null> {
  const db = await openOfflineDb()
  if (!db) return null

  const record: OfflineActionRecord = {
    type: action.type,
    payload: action.payload,
    userId: action.userId,
    timestamp: Date.now(),
  }

  const { promise, resolve } = withResolvers<number | null>()
  try {
    const tx = db.transaction(STORE_ACTIONS, 'readwrite')
    const store = tx.objectStore(STORE_ACTIONS)
    const req = store.add(record)

    req.onsuccess = () => {
      resolve(typeof req.result === 'number' ? req.result : null)
    }
    req.onerror = () => resolve(null)
    tx.onerror = () => resolve(null)
  } catch {
    resolve(null)
  }
  return promise
}

/**
 * 获取所有待回写的离线操作记录
 */
export async function getOfflineActions(): Promise<Required<OfflineActionRecord>[]> {
  const db = await openOfflineDb()
  if (!db) return []

  const { promise, resolve } = withResolvers<Required<OfflineActionRecord>[]>()
  try {
    const tx = db.transaction(STORE_ACTIONS, 'readonly')
    const store = tx.objectStore(STORE_ACTIONS)
    const req = store.getAll()

    req.onsuccess = () => {
      resolve((req.result as Required<OfflineActionRecord>[]) || [])
    }
    req.onerror = () => resolve([])
    tx.onerror = () => resolve([])
  } catch {
    resolve([])
  }
  return promise
}

/**
 * 删除已成功回写的离线操作记录
 */
export async function removeOfflineAction(id: number): Promise<void> {
  const db = await openOfflineDb()
  if (!db || typeof id !== 'number') return

  const { promise, resolve } = withResolvers<void>()
  try {
    const tx = db.transaction(STORE_ACTIONS, 'readwrite')
    const store = tx.objectStore(STORE_ACTIONS)
    store.delete(id)

    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
    tx.onabort = () => resolve()
  } catch {
    resolve()
  }
  return promise
}

/**
 * 清空所有离线操作记录
 */
export async function clearOfflineActions(): Promise<void> {
  const db = await openOfflineDb()
  if (!db) return

  const { promise, resolve } = withResolvers<void>()
  try {
    const tx = db.transaction(STORE_ACTIONS, 'readwrite')
    const store = tx.objectStore(STORE_ACTIONS)
    store.clear()

    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
    tx.onabort = () => resolve()
  } catch {
    resolve()
  }
  return promise
}

/**
 * 彻底清空所有离线元数据数据库
 */
export async function clearAllMetadataDb(): Promise<void> {
  if (dbInstance) {
    dbInstance.close()
    dbInstance = null
  }
  dbOpeningPromise = null

  if (!isIndexedDbSupported()) return

  const { promise, resolve } = withResolvers<void>()
  try {
    const req = indexedDB.deleteDatabase(DB_NAME)
    req.onsuccess = () => resolve()
    req.onerror = () => resolve()
    req.onblocked = () => resolve()
  } catch {
    resolve()
  }
  return promise
}

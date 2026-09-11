import { describe, expect, it, beforeEach } from 'vite-plus/test'
import {
  saveShelfSnapshot,
  getShelfSnapshot,
  saveComicDetail,
  getComicDetail,
  getAllCachedComicDetails,
  enqueueOfflineAction,
  getOfflineActions,
  removeOfflineAction,
  clearOfflineActions,
  clearAllMetadataDb,
} from '@/utils/offlineDb'
import type { ComicDetail, LibrarySummary } from '@/types'

class MockIDBRequest {
  result: unknown = null
  error: unknown = null
  onsuccess: ((ev?: unknown) => void) | null = null
  onerror: ((ev?: unknown) => void) | null = null
  onupgradeneeded: ((ev?: unknown) => void) | null = null
}

class MockIDBObjectStore {
  name: string
  keyPath: string
  autoIncrement: boolean
  data: Map<unknown, unknown> = new Map()
  autoId = 1

  constructor(name: string, options?: { keyPath?: string; autoIncrement?: boolean }) {
    this.name = name
    this.keyPath = options?.keyPath || 'id'
    this.autoIncrement = Boolean(options?.autoIncrement)
  }

  put(value: Record<string, unknown>) {
    const key = value[this.keyPath]
    this.data.set(key, JSON.parse(JSON.stringify(value)))
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = key
      req.onsuccess?.({ target: req })
    })
    return req
  }

  add(value: Record<string, unknown>) {
    let key = value[this.keyPath]
    let storedValue = value
    if (this.autoIncrement) {
      key = this.autoId++
      storedValue = { ...value, [this.keyPath]: key }
    }
    this.data.set(key, JSON.parse(JSON.stringify(storedValue)))
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = key
      req.onsuccess?.({ target: req })
    })
    return req
  }

  get(key: unknown) {
    const val = this.data.get(key)
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = val ? JSON.parse(JSON.stringify(val)) : undefined
      req.onsuccess?.({ target: req })
    })
    return req
  }

  getAll() {
    const list = Array.from(this.data.values()).map((v) => JSON.parse(JSON.stringify(v)))
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = list
      req.onsuccess?.({ target: req })
    })
    return req
  }

  delete(key: unknown) {
    this.data.delete(key)
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = undefined
      req.onsuccess?.({ target: req })
    })
    return req
  }

  clear() {
    this.data.clear()
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = undefined
      req.onsuccess?.({ target: req })
    })
    return req
  }

  count() {
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = this.data.size
      req.onsuccess?.({ target: req })
    })
    return req
  }

  createIndex() {
    return {}
  }

  index() {
    return {
      openCursor: () => {
        const req = new MockIDBRequest()
        queueMicrotask(() => {
          req.result = null
          req.onsuccess?.({ target: req })
        })
        return req
      },
    }
  }
}

class MockIDBTransaction {
  db: MockIDBDatabase
  stores: string[]
  mode: string
  oncomplete: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null

  constructor(db: MockIDBDatabase, stores: string | string[], mode = 'readonly') {
    this.db = db
    this.stores = Array.isArray(stores) ? stores : [stores]
    this.mode = mode

    queueMicrotask(() => {
      this.oncomplete?.()
    })
  }

  objectStore(name: string) {
    return this.db.stores.get(name)!
  }
}

class MockIDBDatabase {
  name: string
  version: number
  stores: Map<string, MockIDBObjectStore> = new Map()
  objectStoreNames: { contains: (n: string) => boolean }
  onversionchange: (() => void) | null = null
  onclose: (() => void) | null = null

  constructor(name: string, version: number) {
    this.name = name
    this.version = version
    this.objectStoreNames = {
      contains: (n: string) => this.stores.has(n),
    }
  }

  createObjectStore(name: string, options?: { keyPath?: string; autoIncrement?: boolean }) {
    const store = new MockIDBObjectStore(name, options)
    this.stores.set(name, store)
    return store
  }

  transaction(storeNames: string | string[], mode?: string) {
    return new MockIDBTransaction(this, storeNames, mode)
  }

  close() {}
}

const mockDatabases = new Map<string, MockIDBDatabase>()

const mockIndexedDB = {
  open(name: string, version = 1) {
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      let db = mockDatabases.get(name)
      const oldVersion = db ? db.version : 0
      if (!db) {
        db = new MockIDBDatabase(name, version)
        mockDatabases.set(name, db)
      }
      req.result = db
      if (version > oldVersion) {
        const event = { oldVersion, newVersion: version }
        req.onupgradeneeded?.(event)
      }
      req.onsuccess?.({ target: req })
    })
    return req
  },
  deleteDatabase(name: string) {
    mockDatabases.delete(name)
    const req = new MockIDBRequest()
    queueMicrotask(() => {
      req.result = undefined
      req.onsuccess?.({ target: req })
    })
    return req
  },
}

function makeMockDetail(sourceId: string): ComicDetail {
  return {
    meta: {
      source: 'jm',
      source_id: sourceId,
      display_id: sourceId,
      title: `Comic ${sourceId}`,
      authors: ['Author 1'],
      works: [],
      actors: [],
      tags: ['Tag1'],
      description: 'Desc',
      uploader: null,
      page_count: 10,
      cover_count: 1,
      cover_indices: [],
      pages: [],
      chapters: [],
      views: '0',
      likes: '0',
      comment_count: 0,
      favorite: false,
      hidden_from_guest: false,
      source_url: '',
      published_at: '',
      updated_at: '',
      imported_at: '',
      last_checked_at: '',
      raw: {},
    },
    cached_pages: 5,
    cache_complete: false,
    cover_paths: ['/cover.jpg'],
  }
}

describe('offlineDb utils', () => {
  beforeEach(async () => {
    ;(globalThis as unknown as { indexedDB: unknown }).indexedDB = mockIndexedDB
    await clearAllMetadataDb()
  })

  it('saves and retrieves shelf snapshots for a user', async () => {
    const mockItems: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: '123',
        display_id: '123',
        title: 'Title 123',
        authors: ['Author A'],
        works: [],
        actors: [],
        tags: ['Tag A'],
        page_count: 20,
        cover_count: 1,
        cover_paths: ['/cover.jpg'],
        cached_pages: 20,
        views: '100',
        likes: '10',
        favorite: true,
        hidden_from_guest: false,
        uploaded_at: '2026-01-01',
        published_at: '2026-01-01',
        updated_at: '2026-01-01',
        imported_at: '2026-01-01',
      },
    ]

    await saveShelfSnapshot('user-1', {
      items: mockItems,
      facets: null,
    })

    const retrieved = await getShelfSnapshot('user-1')
    expect(retrieved).not.toBeNull()
    expect(retrieved?.items).toHaveLength(1)
    expect(retrieved?.items[0]?.title).toBe('Title 123')
  })

  it('falls back to latest snapshot if requested userKey does not match', async () => {
    const mockItems: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: '123',
        display_id: '123',
        title: 'Title 123',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        page_count: 20,
        cover_count: 1,
        cover_paths: ['/cover.jpg'],
        cached_pages: 20,
        views: '100',
        likes: '10',
        favorite: true,
        hidden_from_guest: false,
        uploaded_at: '2026-01-01',
        published_at: '2026-01-01',
        updated_at: '2026-01-01',
        imported_at: '2026-01-01',
      },
    ]

    await saveShelfSnapshot('curator', {
      items: mockItems,
      facets: null,
    })

    // Querying with empty or unknown userId falls back to curator's snapshot
    const retrieved = await getShelfSnapshot('')
    expect(retrieved).not.toBeNull()
    expect(retrieved?.items).toHaveLength(1)
    expect(retrieved?.items[0]?.title).toBe('Title 123')
  })

  it('retrieves all cached comic details', async () => {
    const detail1 = makeMockDetail('comic-1')
    const detail2 = makeMockDetail('comic-2')
    await saveComicDetail('curator', detail1)
    await saveComicDetail('curator', detail2)

    const all = await getAllCachedComicDetails('curator')
    expect(all).toHaveLength(2)

    // Fallback when no userId is passed
    const allFallback = await getAllCachedComicDetails('')
    expect(allFallback).toHaveLength(2)
  })

  it('saves and retrieves comic details with LRU tracking and fallback', async () => {
    const detail = makeMockDetail('comic-999')
    await saveComicDetail('curator', detail)

    const retrieved = await getComicDetail('curator', 'jm', 'comic-999')
    expect(retrieved).not.toBeNull()
    expect(retrieved?.meta.title).toBe('Comic comic-999')

    // Fallback when querying with different or empty userId
    const fallbackRetrieved = await getComicDetail('', 'jm', 'comic-999')
    expect(fallbackRetrieved).not.toBeNull()
    expect(fallbackRetrieved?.meta.title).toBe('Comic comic-999')
  })

  it('enqueues, reads, and deletes offline action records', async () => {
    const actionId = await enqueueOfflineAction({
      type: 'reading_progress',
      payload: { source: 'jm', sourceId: '123', page: 5 },
    })

    expect(typeof actionId).toBe('number')
    expect(actionId).toBeDefined()

    const actions = await getOfflineActions()
    expect(actions).toHaveLength(1)
    expect(actions[0]?.type).toBe('reading_progress')
    expect(actions[0]?.payload.page).toBe(5)

    await removeOfflineAction(actionId as number)
    const afterRemove = await getOfflineActions()
    expect(afterRemove).toHaveLength(0)
  })

  it('clears all offline actions cleanly', async () => {
    await enqueueOfflineAction({
      type: 'favorite',
      payload: { source: 'jm', sourceId: '123', favorite: true },
    })
    await enqueueOfflineAction({
      type: 'reading_progress',
      payload: { source: 'jm', sourceId: '123', page: 2 },
    })

    const actions = await getOfflineActions()
    expect(actions.length).toBe(2)

    await clearOfflineActions()
    const cleared = await getOfflineActions()
    expect(cleared.length).toBe(0)
  })

  it('prevents guest users from accessing hidden_from_guest comics and falling back to curator shelf', async () => {
    // 1. Curator has a snapshot with normal and hidden comics
    const curatorItems: LibrarySummary[] = [
      {
        source: 'jm',
        source_id: 'comic-public',
        title: 'Public Comic',
        display_id: 'comic-public',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        page_count: 10,
        cached_pages: 10,
        cover_count: 1,
        cover_paths: [],
        views: '0',
        likes: '0',
        favorite: false,
        hidden_from_guest: false,
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '',
      },
      {
        source: 'jm',
        source_id: 'comic-hidden',
        title: 'Hidden Comic',
        display_id: 'comic-hidden',
        authors: [],
        works: [],
        actors: [],
        tags: [],
        page_count: 10,
        cached_pages: 10,
        cover_count: 1,
        cover_paths: [],
        views: '0',
        likes: '0',
        favorite: false,
        hidden_from_guest: true,
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '',
      },
    ]
    await saveShelfSnapshot('curator', { items: curatorItems, facets: null })

    // Guest should NOT fall back to curator snapshot
    const guestEmptySnapshot = await getShelfSnapshot('guest:user-123')
    expect(guestEmptySnapshot).toBeNull()

    // 2. If guest has a snapshot, hidden_from_guest items are filtered out
    await saveShelfSnapshot('guest:user-123', { items: curatorItems, facets: null })
    const guestSnapshot = await getShelfSnapshot('guest:user-123')
    expect(guestSnapshot).not.toBeNull()
    expect(guestSnapshot?.items).toHaveLength(1)
    expect(guestSnapshot?.items[0]?.source_id).toBe('comic-public')

    // 3. Guest cannot fetch hidden comic detail directly or via fallback
    const hiddenDetail = makeMockDetail('comic-hidden')
    hiddenDetail.meta.hidden_from_guest = true
    await saveComicDetail('curator', hiddenDetail)

    const guestFetchHidden = await getComicDetail('guest:user-123', 'jm', 'comic-hidden')
    expect(guestFetchHidden).toBeNull()

    // Guest also cannot fallback to curator public comic if not cached for guest
    const guestFetchPublic = await getComicDetail('guest:user-123', 'jm', 'comic-public')
    expect(guestFetchPublic).toBeNull()

    // 4. getAllCachedComicDetails for guest excludes hidden comics and does not cross-tenant fallback
    const guestAll = await getAllCachedComicDetails('guest:user-123')
    expect(guestAll).toHaveLength(0)
  })
})

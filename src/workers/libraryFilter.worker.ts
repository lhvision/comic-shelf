/**
 * @file libraryFilter.worker.ts
 * @description 书架搜索与多维排序后台 Web Worker 线程。
 *
 * 核心设计契约：
 * 1. 内存持有藏书快照，仅在藏书增删改时执行一次全量同步；
 * 2. 检索击键时仅接收微量查询参数（~50 字节），杜绝 structuredClone 序列化风暴；
 * 3. 排序完成后仅向主线程回传轻量 ID 数组（string[]），主线程 O(1) 映射还原。
 */

import { filterAndSortLibraryIds, type FilterParams } from '@/utils/libraryFilterCore'
import type { LibrarySummary } from '@/types'

let storedItems: LibrarySummary[] = []

export interface WorkerInMessage {
  type: 'sync' | 'filter'
  items?: LibrarySummary[]
  params?: FilterParams
  requestId?: number
}

export interface WorkerOutMessage {
  type: 'result'
  idList: string[]
  requestId: number
}

self.onmessage = (event: MessageEvent<WorkerInMessage>) => {
  const data = event.data
  if (!data) return

  if (data.type === 'sync' && Array.isArray(data.items)) {
    storedItems = data.items
  } else if (data.type === 'filter' && data.params && typeof data.requestId === 'number') {
    const idList = filterAndSortLibraryIds(storedItems, data.params)
    const reply: WorkerOutMessage = {
      type: 'result',
      idList,
      requestId: data.requestId,
    }
    self.postMessage(reply)
  }
}

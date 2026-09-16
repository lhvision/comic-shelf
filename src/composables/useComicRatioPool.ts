/**
 * @file useComicRatioPool.ts
 * @description 漫画会话级物理宽高比共享池（Shared Comic Ratio Pool）。
 *
 * 核心职责：
 * 1. 漫画作用域单例映射（Comic-scoped Singleton Map）：
 *    - 基于 comicKey 索引，使主画卷视口（ReaderViewport）、胶片预览轨（ReaderFilmstrip）
 *      与画中画悬停气泡（ReaderHoverPreview）无感互通已解码页面的物理宽高比；
 * 2. 瞬态定盘与防抖（Ratio Latching）：
 *    - 维护全局首张解码页面的基准开本比例（defaultComicRatio），用于未注水纸本骨架与画中画初次弹出的物理撑高；
 * 3. 内存自愈与会话隔离：
 *    - 切换漫画时自动隔离不同作品的比例池，防止跨作品尺寸污染与内存泄漏。
 */

import { computed, ref, type CSSProperties, type Ref } from 'vue'

export interface ComicRatioPoolEntry {
  pageRatios: Map<number, string>
  defaultRatio: Ref<string | null>
}

const MAX_POOL_ENTRIES = 24
const pool = new Map<string, ComicRatioPoolEntry>()

/**
 * 获取或创建指定漫画的宽高比池单例条目
 * @param key 漫画唯一标识（如 "source/source_id"）
 */
export function getOrCreatePoolEntry(key: string): ComicRatioPoolEntry {
  let entry = pool.get(key)
  if (entry) {
    // 命中缓存：重置位置刷新至 Map 末尾以维持真实 LRU 淘汰顺序
    pool.delete(key)
    pool.set(key, entry)
    return entry
  }
  if (pool.size >= MAX_POOL_ENTRIES) {
    const oldestKey = pool.keys().next().value
    if (oldestKey) {
      pool.delete(oldestKey)
    }
  }
  entry = {
    pageRatios: new Map<number, string>(),
    defaultRatio: ref<string | null>(null),
  }
  pool.set(key, entry)
  return entry
}

/**
 * 清空指定漫画的宽高比池
 * @param key 漫画唯一标识
 */
export function clearPoolEntry(key: string): void {
  pool.delete(key)
}

/**
 * 跨组件共享的漫画宽高比池 Composable
 * @param comicKey 漫画唯一业务键（Ref）
 * @returns 宽高比池操作方法与响应式状态
 */
export function useComicRatioPool(comicKey: Ref<string>) {
  const defaultComicRatio = computed<string | null>({
    get: () => getOrCreatePoolEntry(comicKey.value).defaultRatio.value,
    set: (v) => {
      getOrCreatePoolEntry(comicKey.value).defaultRatio.value = v
    },
  })

  /**
   * 记录单页图片的物理自然宽高比
   * @param page 全局页码
   * @param ratio 宽高比字符串（如 "800 / 1200"）
   */
  function setPageRatio(page: number, ratio?: string | null) {
    if (ratio && Number.isFinite(page) && page > 0) {
      const entry = getOrCreatePoolEntry(comicKey.value)
      entry.pageRatios.set(page, ratio)
      if (!entry.defaultRatio.value) {
        entry.defaultRatio.value = ratio
      }
    }
  }

  /**
   * 获取指定页码或默认漫画宽高比计算得出的 CSSProperties 样式
   * @param page 全局页码
   */
  function getPageStyle(page: number): CSSProperties | undefined {
    const entry = getOrCreatePoolEntry(comicKey.value)
    const ratio = entry.pageRatios.get(page) ?? entry.defaultRatio.value
    return ratio
      ? ({
          '--quiescent-ratio': ratio,
          aspectRatio: ratio,
        } as CSSProperties)
      : undefined
  }

  /**
   * 获取指定页码已记录的物理比例，若未命中则回退默认比例
   * @param page 全局页码
   */
  function getPageRatio(page: number): string | null {
    const entry = getOrCreatePoolEntry(comicKey.value)
    return entry.pageRatios.get(page) ?? entry.defaultRatio.value
  }

  return {
    defaultComicRatio,
    setPageRatio,
    getPageRatio,
    getPageStyle,
  }
}

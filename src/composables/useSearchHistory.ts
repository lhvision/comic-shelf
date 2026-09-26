/**
 * @file useSearchHistory.ts
 * @description 书架搜索历史沉淀与快捷复用组合式函数。
 *
 * 核心特性：
 * 1. 端侧持久化：基于 VueUse useLocalStorage 将搜索历史持久化于 localStorage('comic-shelf:search-history:v1')；
 * 2. LRU 淘汰与防重复：最多保留 8 条记录，重复检索自动置顶，超出自动淘汰最旧项；
 * 3. 快捷指令多态支持：支持沉淀带参快捷指令（如 /台词、/作者、/车号），排除无参即时动作（/随机）；
 * 4. 纯净管理能力：提供 addHistory、removeHistory、clearHistory 规范方法。
 */

import { watch, type Ref } from 'vue'
import { createGlobalState, useLocalStorage } from '@vueuse/core'
import type { SearchCommandType } from '@/composables/useSearchCommands'

export const SEARCH_HISTORY_KEY = 'comic-shelf:search-history:v1'
export const MAX_SEARCH_HISTORY = 8
export const MAX_QUERY_LENGTH = 100

export interface SearchHistoryItem {
  id: string
  query: string
  command?: SearchCommandType | null
  timestamp: number
}

export interface UseSearchHistoryReturn {
  /** 当前持久化的搜索历史条目列表（按最近时间倒序） */
  history: Ref<SearchHistoryItem[]>
  /** 添加/更新一条搜索历史（自动去重并置顶，超出 8 条淘汰最旧项） */
  addHistory: (query: string, command?: SearchCommandType | null) => void
  /** 移除指定 ID 的历史条目 */
  removeHistory: (id: string) => void
  /** 清空全部搜索历史 */
  clearHistory: () => void
}

export function isValidHistoryItem(item: unknown): item is SearchHistoryItem {
  if (!item || typeof item !== 'object') return false
  const candidate = item as Partial<SearchHistoryItem>
  const isValidCommand =
    candidate.command === undefined ||
    candidate.command === null ||
    candidate.command === 'dialogue' ||
    candidate.command === 'id' ||
    candidate.command === 'author'
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.query === 'string' &&
    candidate.query.trim().length > 0 &&
    typeof candidate.timestamp === 'number' &&
    Number.isFinite(candidate.timestamp) &&
    isValidCommand
  )
}

export const useSearchHistory = createGlobalState((): UseSearchHistoryReturn => {
  const history = useLocalStorage<SearchHistoryItem[]>(SEARCH_HISTORY_KEY, [])

  // 启动与运行时防脏监听：首帧与多标签页联动清洗外部非法写入
  watch(
    history,
    (val) => {
      if (!Array.isArray(val)) {
        history.value = []
      } else {
        const valid = val.filter(isValidHistoryItem)
        if (valid.length !== val.length) {
          history.value = valid
        }
      }
    },
    { immediate: true, deep: true },
  )

  function addHistory(query: string, command?: SearchCommandType | null): void {
    const trimmed = query.trim().slice(0, MAX_QUERY_LENGTH)
    if (!trimmed) {
      return
    }
    // 排除无参数即时动作（如 /随机 抽一本）
    if (command === 'random') {
      return
    }
    // 排除未激活指令模式下的斜杠指令语法（如打字未决中途点击或误回车产生的 / 或 /未知指令）
    if (!command && trimmed.startsWith('/')) {
      return
    }

    if (!Array.isArray(history.value)) {
      history.value = []
    }

    const cleanHistory = history.value.filter(isValidHistoryItem)
    const targetCmd = command || null
    const existingIndex = cleanHistory.findIndex(
      (item) =>
        item.query.toLowerCase() === trimmed.toLowerCase() && (item.command || null) === targetCmd,
    )

    const newItem: SearchHistoryItem = {
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      query: trimmed,
      command: targetCmd,
      timestamp: Date.now(),
    }

    const updated = [...cleanHistory]
    if (existingIndex !== -1) {
      updated.splice(existingIndex, 1)
    }
    updated.unshift(newItem)

    history.value = updated.slice(0, MAX_SEARCH_HISTORY)
  }

  function removeHistory(id: string): void {
    if (!Array.isArray(history.value)) {
      history.value = []
      return
    }
    history.value = history.value.filter((item) => isValidHistoryItem(item) && item.id !== id)
  }

  function clearHistory(): void {
    history.value = []
  }

  return {
    history,
    addHistory,
    removeHistory,
    clearHistory,
  }
})

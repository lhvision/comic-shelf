/**
 * @file useReaderRecommendations.ts
 * @description 阅读器末页接卷推荐（Next Reads）选书算法与组合式函数。
 *
 * 核心选书逻辑：
 * 1. 过滤候选池：排除当前漫画本身，排除全部已读完作品（last_page >= page_count）；
 * 2. 相关度打分：
 *    - 同作者（authors 交集）：每命中一个 +10 分；
 *    - 同原作/系列（works 交集）：每命中一个 +10 分；
 *    - 共有标签（tags 交集）：每命中一个 +2 分；
 *    - 在读状态加权（0 < last_page < page_count）：+1 分（鼓励清空在读积压）；
 * 3. 排序规则：得分从高到低，平分按 imported_at 倒序兜底；
 * 4. 截取前 count 本。
 */

import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import type { LibrarySummary } from '@/types'
import { isCompletedComic } from '@/composables/useLibraryFilter'

export interface RecommendTarget {
  source: string
  source_id: string
  authors?: string[]
  works?: string[]
  tags?: string[]
}

/**
 * 纯函数：根据当前漫画特征与书库藏书计算推荐列表
 */
export function computeRecommendations(
  current: RecommendTarget,
  allItems: LibrarySummary[],
  count = 3,
): LibrarySummary[] {
  if (!allItems || allItems.length === 0) return []

  const currentAuthors = new Set((current.authors || []).map((a) => a.trim().toLowerCase()))
  const currentWorks = new Set((current.works || []).map((w) => w.trim().toLowerCase()))
  const currentTags = new Set((current.tags || []).map((t) => t.trim().toLowerCase()))

  // 1. 候选池：排除当前本，排除已读完本
  const candidates = allItems.filter((item) => {
    if (item.source === current.source && item.source_id === current.source_id) {
      return false
    }
    if (isCompletedComic(item)) {
      return false
    }
    return true
  })

  // 2. 打分
  const scored = candidates.map((item) => {
    let score = 0

    // 作者关联
    for (const a of item.authors || []) {
      if (currentAuthors.has(a.trim().toLowerCase())) {
        score += 10
      }
    }

    // 原作/系列关联
    for (const w of item.works || []) {
      if (currentWorks.has(w.trim().toLowerCase())) {
        score += 10
      }
    }

    // 标签共有重合度
    for (const t of item.tags || []) {
      if (currentTags.has(t.trim().toLowerCase())) {
        score += 2
      }
    }

    // 在读状态微加权（优先引导读完在读书卷）
    if ((item.last_page ?? 0) > 0 && (item.last_page ?? 0) < item.page_count) {
      score += 1
    }

    return { item, score }
  })

  // 3. 排序：得分从高到低，得分相同时按最新收录时间倒序
  scored.sort((a, b) => {
    if (b.score !== a.score) {
      return b.score - a.score
    }
    return new Date(b.item.imported_at || 0).getTime() - new Date(a.item.imported_at || 0).getTime()
  })

  return scored.slice(0, count).map((s) => s.item)
}

/**
 * 接卷推荐 Composable
 */
export function useReaderRecommendations(
  current: MaybeRefOrGetter<RecommendTarget | null | undefined>,
  allItems: MaybeRefOrGetter<LibrarySummary[]>,
  count = 3,
) {
  const recommendations = computed(() => {
    const cur = toValue(current)
    const items = toValue(allItems)
    if (!cur) return []
    return computeRecommendations(cur, items, count)
  })

  return {
    recommendations,
  }
}

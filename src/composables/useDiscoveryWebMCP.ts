/**
 * @file useDiscoveryWebMCP.ts
 * @description 发现与排行榜视口前端模型上下文协议（WebMCP）工具注册组合式函数。
 *
 * 核心设计与架构定位：
 * 1. 【发现与精选排行榜操作面 (Discovery Viewport-Scoped Tools)】：
 *    在 DiscoveryView 挂载期间向浏览器 AI Agent 暴露官方排行榜榜单获取、时间跨度切换（周榜/月榜/日榜）、
 *    榜单漫画一键收录至本地书库及已收录漫画直达工具；
 * 2. 【生命周期隔离】：
 *    离开发现页面时自动注销工具。
 */

import { type Ref, type ShallowRef } from 'vue'
import { useWebMCP } from '@vueuse/core'
import type { Router } from 'vue-router'
import type { DiscoveryFeed, DiscoveryItem, DiscoveryTimeframe } from '@/types'

/**
 * `useDiscoveryWebMCP` 依赖项契约
 */
export interface UseDiscoveryWebMCPOptions {
  /** 当前选中的时间跨度 */
  timeframe: Ref<DiscoveryTimeframe>
  /** 排行榜数据 Ref */
  feed: ShallowRef<DiscoveryFeed | null>
  /** 加载排行榜方法 */
  loadRanking: (tf?: DiscoveryTimeframe, refresh?: boolean) => Promise<void>
  /** 收录漫画方法 */
  ingestComic: (item: DiscoveryItem) => Promise<void>
  /** 路由实例 */
  router: Router
}

/**
 * 在发现视图挂载期间注册 WebMCP 排行榜交互工具集
 */
export function useDiscoveryWebMCP(options: UseDiscoveryWebMCPOptions) {
  const { timeframe, feed, loadRanking, ingestComic, router } = options

  // 工具 1: 获取官方精选排行榜
  const getRankingTool = useWebMCP({
    name: 'discovery_get_ranking',
    description:
      '获取禁漫官方精选与排行数据。返回榜单列表、作品标题、作者、分类标签及是否已收录在本地书库的状态',
    inputSchema: {
      type: 'object',
      properties: {
        timeframe: {
          type: 'string',
          enum: ['week', 'month', 'day'],
          description:
            '榜单时间跨度：week（本周必看/周榜）、month（本月热门/月榜）、day（今日精选/日榜）',
        },
        refresh: {
          type: 'boolean',
          description: '是否强制刷新远端官方排行榜数据（默认 false 读取缓存）',
        },
      },
    },
    async execute(args) {
      const { timeframe: targetTf, refresh } = (args ?? {}) as {
        timeframe?: DiscoveryTimeframe
        refresh?: boolean
      }

      if (targetTf === 'week' || targetTf === 'month' || targetTf === 'day') {
        await loadRanking(targetTf, Boolean(refresh))
      } else if (refresh) {
        await loadRanking(timeframe.value, true)
      }

      const items = feed.value?.items || []
      return {
        success: true,
        timeframe: timeframe.value,
        total: items.length,
        items: items.map((it) => ({
          id: it.id,
          source: it.source,
          source_id: it.source_id,
          title: it.title,
          author: it.author,
          category: it.category,
          in_library: Boolean(it.in_library),
        })),
      }
    },
  })

  // 工具 2: 切换排行榜分类标签
  const switchTimeframeTool = useWebMCP({
    name: 'discovery_switch_timeframe',
    description: '切换官方精选榜单的时间跨度分类标签（周榜 / 月榜 / 日榜）',
    inputSchema: {
      type: 'object',
      properties: {
        timeframe: {
          type: 'string',
          enum: ['week', 'month', 'day'],
          description: '目标时间跨度：week 为本周必看，month 为本月热门，day 为今日精选',
        },
      },
      required: ['timeframe'],
    },
    async execute(args) {
      const { timeframe: targetTf } = (args ?? {}) as { timeframe?: DiscoveryTimeframe }
      if (targetTf !== 'week' && targetTf !== 'month' && targetTf !== 'day') {
        throw new Error('参数 "timeframe" 必须为 "week"、"month" 或 "day"。')
      }

      await loadRanking(targetTf, false)
      return {
        success: true,
        message: `已切换至 ${targetTf === 'week' ? '周榜（本周必看）' : targetTf === 'month' ? '月榜（本月热门）' : '日榜（今日精选）'}`,
        timeframe: targetTf,
      }
    },
  })

  // 工具 3: 一键收录榜单中的漫画至本地书库
  const ingestComicTool = useWebMCP({
    name: 'discovery_ingest_comic',
    description: '一键将排行榜中的指定漫画收录导入至本地书库（会自动在后台开启预缓存）',
    inputSchema: {
      type: 'object',
      properties: {
        source_id: {
          type: 'string',
          description: '榜单中漫画的车号或唯一作品 ID（例如 "523607"）',
        },
      },
      required: ['source_id'],
    },
    async execute(args) {
      const { source_id } = (args ?? {}) as { source_id?: string }
      if (!source_id) {
        throw new Error('参数 "source_id" 为必填项。')
      }

      const items = feed.value?.items || []
      const targetItem = items.find((it) => it.source_id === source_id)
      if (!targetItem) {
        throw new Error(`未在当前排行榜中找到车号为 "${source_id}" 的漫画。`)
      }

      await ingestComic(targetItem)
      return {
        success: true,
        message: `已成功将榜单漫画《${targetItem.title}》（车号：${source_id}）收录至本地书库`,
        comic: {
          source: targetItem.source,
          source_id: targetItem.source_id,
          title: targetItem.title,
          author: targetItem.author,
        },
      }
    },
  })

  // 工具 4: 查看已收录漫画详情
  const openDetailTool = useWebMCP({
    name: 'discovery_open_detail',
    description: '导航进入榜单中某本漫画的详情页',
    inputSchema: {
      type: 'object',
      properties: {
        source: {
          type: 'string',
          description: '漫画图源 Provider（默认 "jm"）',
        },
        source_id: {
          type: 'string',
          description: '漫画车号或作品 ID',
        },
      },
      required: ['source_id'],
    },
    async execute(args) {
      const { source = 'jm', source_id } = (args ?? {}) as {
        source?: string
        source_id?: string
      }
      if (!source_id) {
        throw new Error('参数 "source_id" 为必填项。')
      }

      await router.push({
        name: 'comic-detail',
        params: { source, sourceId: source_id },
      })

      return {
        success: true,
        message: `已导航至漫画 ${source}/${source_id} 详情页`,
      }
    },
  })

  return {
    isSupported: getRankingTool.isSupported,
    getRankingTool,
    switchTimeframeTool,
    ingestComicTool,
    openDetailTool,
  }
}

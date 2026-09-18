/**
 * @file useShelfWebMCP.ts
 * @description 书架首页视口前端模型上下文协议（WebMCP）全功能工具注册组合式函数。
 *
 * 核心设计与架构定位：
 * 1. 【案头淘书全功能操作面 (Shelf Viewport-Scoped Tools)】：
 *    在 LibraryView 挂载期间向浏览器 AI Agent 暴露淘书筛选、台词全文检索、随手翻一本与藏书直达工具；
 *    Agent 可直接发送结构化查询（关键词、标签、图源 Provider、排序维度、阅读状态）或直达指定本子详情页，
 *    无需模拟打字或在 DOM 树中寻找复杂的分类标签与搜索框。
 * 2. 【生命周期与安全隔离】：
 *    离开书架页面时工具自动销毁，避免在详情或阅读器中误触全局书架重置。
 */

import { useWebMCP } from '@vueuse/core'
import type { Router } from 'vue-router'
import { api } from '@/api/client'
import { useShelfState } from '@/composables/useShelfState'
import { useLibraryStore } from '@/stores/library'
import type { ReadingStatus, SortKey } from '@/types'

/**
 * `useShelfWebMCP` 依赖项契约
 */
export interface UseShelfWebMCPOptions {
  /** 路由实例，用于页面跳转 */
  router: Router
}

/**
 * 在书架视图生命周期内注册 WebMCP 淘书、检索与直达全功能工具集
 */
export function useShelfWebMCP(options: UseShelfWebMCPOptions) {
  const { router } = options
  const shelfState = useShelfState()
  const store = useLibraryStore()

  // 工具 1: 书架多维淘书与全字段检索
  const searchComicsTool = useWebMCP({
    name: 'shelf_search_comics',
    description:
      '多维检索与过滤书架中的漫画藏书。支持按标题/作者关键词、分类标签、排序规则、红心收藏标记以及阅读进度综合筛选',
    inputSchema: {
      type: 'object',
      properties: {
        keyword: {
          type: 'string',
          description: '搜索关键词（模糊匹配漫画标题、作者名称或车号 ID）',
        },
        tag: {
          type: 'string',
          description: '分类题材标签（例如 "同人", "恋爱", "动作"）',
        },
        sortBy: {
          type: 'string',
          enum: ['recent', 'title', 'pages', 'cached'],
          description:
            '书架排序维度：recent(最近阅读), title(标题名称), pages(页数多少), cached(缓存完成度)',
        },
        favoritesOnly: {
          type: 'boolean',
          description: '是否仅展示已加入红心收藏的漫画',
        },
        readingStatus: {
          type: 'string',
          enum: ['all', 'reading', 'completed', 'unread'],
          description:
            '按阅读进度筛选：all(全部藏书), reading(在读中), completed(已读完归档), unread(未读新入)',
        },
      },
    },
    async execute(args) {
      const { keyword, tag, sortBy, favoritesOnly, readingStatus } = (args ?? {}) as {
        keyword?: string
        tag?: string
        sortBy?: SortKey
        favoritesOnly?: boolean
        readingStatus?: ReadingStatus
      }

      if (typeof keyword === 'string') {
        shelfState.search.value = keyword.trim()
      }
      if (typeof tag === 'string') {
        if (tag.trim() === '') {
          shelfState.activeTags.value = []
        } else {
          shelfState.activeTags.value = [tag.trim()]
        }
      }
      if (sortBy === 'recent' || sortBy === 'title' || sortBy === 'pages' || sortBy === 'cached') {
        shelfState.sortBy.value = sortBy
      }
      if (typeof favoritesOnly === 'boolean') {
        shelfState.favoritesOnly.value = favoritesOnly
      }
      if (
        readingStatus === 'all' ||
        readingStatus === 'reading' ||
        readingStatus === 'completed' ||
        readingStatus === 'unread'
      ) {
        shelfState.readingStatus.value = readingStatus
      }

      return {
        success: true,
        message: '已成功更新书架检索过滤条件',
        currentFilters: {
          keyword: shelfState.search.value,
          tags: shelfState.activeTags.value,
          sortBy: shelfState.sortBy.value,
          favoritesOnly: shelfState.favoritesOnly.value,
          readingStatus: shelfState.readingStatus.value,
        },
      }
    },
  })

  // 工具 2: 全库分镜台词全文检索（SQLite FTS5）
  const searchDialogueTool = useWebMCP({
    name: 'shelf_search_dialogue',
    description:
      '基于 SQLite FTS5 全文索引，在全站漫画分镜中全文检索台词与对话，并返回匹配的漫画画页与气泡坐标',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: '要检索的台词或对白关键词（至少 2 个字符）',
        },
        source: {
          type: 'string',
          description: '可选的图源 Provider 过滤（如 "jm", "local", "picacg"）',
        },
        limit: {
          type: 'number',
          description: '最大返回匹配条数（默认 10）',
        },
      },
      required: ['query'],
    },
    async execute(args) {
      const {
        query,
        source,
        limit = 10,
      } = (args ?? {}) as {
        query?: string
        source?: string
        limit?: number
      }
      const trimmed = (query ?? '').trim()
      if (trimmed.length < 2) {
        throw new Error('台词搜索关键词至少需要 2 个字符。')
      }

      const response = await api.searchDialogue(trimmed, source, limit)
      return {
        success: true,
        total: response.total,
        matches: response.results.map((item) => ({
          source: item.source,
          source_id: item.source_id,
          title: item.title,
          page_index: item.page_index,
          dialogue_text: item.text,
          bubble_box: item.box,
        })),
      }
    },
  })

  // 工具 3: 随手翻一本（随机挑选）
  const pickRandomTool = useWebMCP({
    name: 'shelf_pick_random',
    description:
      '从当前书架藏书中随机淘选一本漫画，并直接导航进入其详情页（适合漫无目的时随手翻一本）',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    async execute() {
      const items = store.items
      if (!items || items.length === 0) {
        throw new Error('当前书架为空，无可淘选的漫画。')
      }
      const randomIndex = Math.floor(Math.random() * items.length)
      const picked = items[randomIndex]
      if (!picked) {
        throw new Error('随机抽选漫画失败。')
      }

      await router.push({
        name: 'comic-detail',
        params: { source: picked.source, sourceId: picked.source_id },
      })

      return {
        success: true,
        message: `已随机淘选漫画《${picked.title}》(${picked.source}/${picked.source_id}) 并进入详情页`,
        comic: {
          source: picked.source,
          source_id: picked.source_id,
          title: picked.title,
          page_count: picked.page_count,
        },
      }
    },
  })

  // 工具 4: 打开指定藏书详情
  const openComicTool = useWebMCP({
    name: 'shelf_open_comic',
    description: '通过图源 Provider 和漫画车号 ID 直达打开指定漫画的详情页',
    inputSchema: {
      type: 'object',
      properties: {
        source: {
          type: 'string',
          description: '漫画图源 Provider（例如 "jm", "local", "picacg"）',
        },
        source_id: {
          type: 'string',
          description: '漫画唯一车号或作品 ID',
        },
      },
      required: ['source', 'source_id'],
    },
    async execute(args) {
      const { source, source_id } = (args ?? {}) as {
        source?: string
        source_id?: string
      }
      if (!source || !source_id) {
        throw new Error('参数 "source" 与 "source_id" 均为必填项。')
      }

      await router.push({
        name: 'comic-detail',
        params: { source, sourceId: source_id },
      })

      return {
        success: true,
        message: `已导航直达漫画 ${source}/${source_id} 详情页`,
      }
    },
  })

  // 工具 5: 直达阅读器指定画页与分镜气泡
  const readComicTool = useWebMCP({
    name: 'shelf_read_comic',
    description:
      '直接从书架打开指定漫画并跳转到特定画页阅读，可附带对白气泡坐标进行高亮聚焦（非常适合台词搜索命中后一键直达分镜）',
    inputSchema: {
      type: 'object',
      properties: {
        source: {
          type: 'string',
          description: '漫画图源 Provider（例如 "jm", "local", "picacg"）',
        },
        source_id: {
          type: 'string',
          description: '漫画唯一车号或作品 ID',
        },
        page: {
          type: 'number',
          description: '目标画页的 1-based 全局页码（默认第 1 页）',
        },
        bubble_box: {
          type: 'array',
          items: { type: 'number' },
          description: '可选的对白气泡归一化坐标 [ymin, xmin, ymax, xmax]（0..1 范围）',
        },
        bubble_text: {
          type: 'string',
          description: '可选的对白台词文本片段',
        },
      },
      required: ['source', 'source_id'],
    },
    async execute(args) {
      const {
        source,
        source_id,
        page = 1,
        bubble_box,
        bubble_text,
      } = (args ?? {}) as {
        source?: string
        source_id?: string
        page?: number
        bubble_box?: number[]
        bubble_text?: string
      }
      if (!source || !source_id) {
        throw new Error('参数 "source" 与 "source_id" 均为必填项。')
      }

      const queryObj: Record<string, string> = {}
      if (Array.isArray(bubble_box) && bubble_box.length === 4) {
        queryObj.bubble_box = bubble_box.map((v) => Number(v).toFixed(4)).join(',')
      }
      if (bubble_text) {
        queryObj.bubble_text = bubble_text
      }
      if (bubble_box || bubble_text) {
        queryObj.highlight_bubble = '1'
      }

      await router.push({
        path: `/comic/${encodeURIComponent(source)}/${encodeURIComponent(source_id)}/read/${page}`,
        query: queryObj,
      })

      return {
        success: true,
        message: `已直达漫画 ${source}/${source_id} 第 ${page} 页阅读器${bubble_text ? ` 并高亮气泡：“${bubble_text}”` : ''}`,
        source,
        source_id,
        page,
      }
    },
  })

  // 工具 6: 全库以图搜图（基于视觉向量特征检索画页与相似度）
  const searchImageTool = useWebMCP({
    name: 'shelf_search_image',
    description:
      '通过传入图片的 Base64 编码数据在全站漫画库中进行以图搜图（视觉向量匹配），精准定位到所属漫画、画页页码及相似度评分',
    inputSchema: {
      type: 'object',
      properties: {
        image_base64: {
          type: 'string',
          description: '待检索图片的 Base64 编码字符串（支持带或不带 data:image/...;base64, 前缀）',
        },
      },
      required: ['image_base64'],
    },
    async execute(args) {
      const { image_base64 } = (args ?? {}) as { image_base64?: string }
      if (!image_base64 || !image_base64.trim()) {
        throw new Error('参数 "image_base64" 为必填项。')
      }

      let file: File
      try {
        const dataUri = image_base64.startsWith('data:')
          ? image_base64
          : `data:image/jpeg;base64,${image_base64.trim()}`
        const res = await fetch(dataUri)
        const blob = await res.blob()
        file = new File([blob], 'search.jpg', { type: blob.type || 'image/jpeg' })
      } catch {
        const commaIdx = image_base64.indexOf(',')
        const rawBase64 = commaIdx >= 0 ? image_base64.slice(commaIdx + 1) : image_base64
        const byteCharacters = atob(rawBase64.trim())
        const byteNumbers = new Uint8Array(byteCharacters.length)
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i)
        }
        file = new File([byteNumbers], 'search.jpg', { type: 'image/jpeg' })
      }

      const results = await api.imageSearch(file)
      return {
        success: true,
        total: results.length,
        matches: results.map((item) => ({
          source: item.source,
          source_id: item.source_id,
          page_index: item.page_index,
          is_cover: item.is_cover,
          similarity: `${Math.round(item.score * 100)}%`,
          score: item.score,
        })),
      }
    },
  })

  // 工具 7: 收录/导入新漫画至本地书库
  const importComicTool = useWebMCP({
    name: 'shelf_import_comic',
    description:
      '通过图源 Provider 和漫画车号/作品 ID 将远端漫画收录导入至本地书库（会自动触发元数据解析与后台首批预缓存）',
    inputSchema: {
      type: 'object',
      properties: {
        source: {
          type: 'string',
          description: '漫画图源 Provider（例如 "jm", "picacg", "local"）',
        },
        source_id: {
          type: 'string',
          description: '漫画车号或唯一作品 ID（例如 "523607"）',
        },
      },
      required: ['source', 'source_id'],
    },
    async execute(args) {
      const { source, source_id } = (args ?? {}) as {
        source?: string
        source_id?: string
      }
      if (!source || !source_id) {
        throw new Error('参数 "source" 与 "source_id" 均为必填项。')
      }

      const result = await store.importComic({
        id: source_id,
        source,
      })

      return {
        success: true,
        message: `已成功收录漫画《${result.meta.title}》（车号：${result.meta.display_id || result.meta.source_id}）`,
        comic: {
          source: result.meta.source,
          source_id: result.meta.source_id,
          title: result.meta.title,
          page_count: result.meta.page_count,
          from_cache: result.from_cache,
        },
      }
    },
  })

  return {
    isSupported: searchComicsTool.isSupported,
    searchComicsTool,
    searchDialogueTool,
    searchImageTool,
    pickRandomTool,
    openComicTool,
    readComicTool,
    importComicTool,
  }
}

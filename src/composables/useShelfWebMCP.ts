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

import { ref } from 'vue'
import { useWebMCP } from '@vueuse/core'
import type { Router } from 'vue-router'
import { api } from '@/api/client'
import { useAuth } from '@/composables/useAuth'
import {
  MAX_HIGHLIGHT_BOXES,
  serializeBubbleBox,
  serializeBubbleBoxes,
} from '@/composables/useReaderBubble'
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

import type { WebMCPComposableReturn } from '@/types'

export type UseShelfWebMCPReturn = WebMCPComposableReturn<
  | 'searchComicsTool'
  | 'searchDialogueTool'
  | 'searchImageTool'
  | 'pickRandomTool'
  | 'openComicTool'
  | 'readComicTool'
  | 'importComicTool'
>

/**
 * 在书架视图生命周期内注册 WebMCP 淘书、检索与直达全功能工具集
 */
export function useShelfWebMCP(options: UseShelfWebMCPOptions): UseShelfWebMCPReturn {
  const { router } = options
  const shelfState = useShelfState()
  const store = useLibraryStore()
  const { canWrite, isDirectPass } = useAuth()

  // 单本沙箱临时受访者：彻底关停 WebMCP，避免外部自动化脚本穿透与高频抓取
  if (isDirectPass.value) {
    return {
      isSupported: ref(false),
    }
  }

  // 工具 1: 书架多维淘书与全字段检索
  const searchComicsTool = useWebMCP({
    name: 'shelf_search_comics',
    description:
      '多维检索与过滤书架中的漫画藏书。支持按标题/作者关键词、单标签/多标签组合、排序规则、红心收藏标记以及阅读进度综合筛选',
    inputSchema: {
      type: 'object',
      properties: {
        keyword: {
          type: 'string',
          description: '搜索关键词（模糊匹配漫画标题、作者名称或车号 ID）',
        },
        tag: {
          type: 'string',
          description: '单个分类题材标签（例如 "同人", "恋爱", "动作"）',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: '多标签复合筛选列表（多标签取交集 AND 筛选）',
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
        reset: {
          type: 'boolean',
          description: '在应用新条件前是否先清空重置当前已有筛选过滤条件（默认 false）',
        },
      },
    },
    async execute(args) {
      const { keyword, tag, tags, sortBy, favoritesOnly, readingStatus, reset } = (args ?? {}) as {
        keyword?: string
        tag?: string
        tags?: string[]
        sortBy?: SortKey
        favoritesOnly?: boolean
        readingStatus?: ReadingStatus
        reset?: boolean
      }

      if (reset) {
        shelfState.resetShelfFilters()
      }

      if (typeof keyword === 'string') {
        shelfState.search.value = keyword.trim()
      }
      if (Array.isArray(tags)) {
        shelfState.activeTags.value = tags.map((t) => String(t).trim()).filter(Boolean)
      } else if (typeof tag === 'string') {
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
          bubble_count: item.bubble_count,
          other_boxes: item.other_boxes,
          rank_score: item.rank_score,
        })),
      }
    },
  })

  // 工具 3: 随手翻一本（随机挑选）
  const pickRandomTool = useWebMCP({
    name: 'shelf_pick_random',
    description:
      '从当前书架藏书中随机淘选一本漫画。支持限定已收藏或特定图源，并可选择直达详情页或直接进入阅读器',
    inputSchema: {
      type: 'object',
      properties: {
        favoritesOnly: {
          type: 'boolean',
          description: '是否仅在红心收藏的漫画中随机抽选（默认 false）',
        },
        source: {
          type: 'string',
          enum: ['jm', 'picacg', 'local'],
          description: '可选限定图源平台（如 "jm" | "picacg" | "local"）',
        },
        openReader: {
          type: 'boolean',
          description:
            '是否直接打开阅读器开始阅读（true 直达阅读器，false 直达详情页，默认 false）',
        },
      },
    },
    async execute(args) {
      const { favoritesOnly, source, openReader } = (args ?? {}) as {
        favoritesOnly?: boolean
        source?: string
        openReader?: boolean
      }

      let candidates = store.items || []
      if (favoritesOnly) {
        candidates = candidates.filter((item) => item.favorite)
      }
      if (source) {
        candidates = candidates.filter((item) => item.source === source)
      }

      if (candidates.length === 0) {
        throw new Error('未找到符合条件的候选漫画。')
      }
      const randomIndex = Math.floor(Math.random() * candidates.length)
      const picked = candidates[randomIndex]
      if (!picked) {
        throw new Error('随机抽选漫画失败。')
      }

      if (openReader) {
        await router.push({
          path: `/comic/${encodeURIComponent(picked.source)}/${encodeURIComponent(picked.source_id)}/read/1`,
        })
      } else {
        await router.push({
          name: 'comic-detail',
          params: { source: picked.source, sourceId: picked.source_id },
        })
      }

      return {
        success: true,
        message: `已随机淘选漫画《${picked.title}》（${picked.source}/${picked.source_id}）并${openReader ? '进入阅读器' : '进入详情页'}`,
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
    description: '通过图源 Provider 和漫画车号 ID 直达打开指定漫画的详情页或章节子路由页',
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
        chapter_id: {
          type: 'string',
          description: '可选直达的章节 ID（例如 "c1", "c2"）',
        },
      },
      required: ['source', 'source_id'],
    },
    async execute(args) {
      const { source, source_id, chapter_id } = (args ?? {}) as {
        source?: string
        source_id?: string
        chapter_id?: string
      }
      if (!source || !source_id) {
        throw new Error('参数 "source" 与 "source_id" 均为必填项。')
      }

      if (chapter_id) {
        await router.push(`/comic/${source}/${source_id}/chapter/${chapter_id}`)
      } else {
        await router.push({
          name: 'comic-detail',
          params: { source, sourceId: source_id },
        })
      }

      return {
        success: true,
        message: `已导航直达漫画 ${source}/${source_id}${chapter_id ? ` 章节 ${chapter_id}` : ''} 页面`,
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
        fromBeginning: {
          type: 'boolean',
          description: '是否强制从第 1 页开始（忽略上次历史进度）',
        },
        chapter_id: {
          type: 'string',
          description: '可选指定章节 ID',
        },
        bubble_box: {
          type: 'array',
          items: { type: 'number' },
          description: '可选的对白气泡归一化坐标 [ymin, xmin, ymax, xmax]（0..1 范围）',
        },
        other_boxes: {
          type: 'array',
          items: { type: 'array', items: { type: 'number' } },
          // 前端这份与阅读器解析侧共用 MAX_HIGHLIGHT_BOXES；后端 MAX_PAGE_BOXES（检索结果与
          // MCP 直达链接的封顶）同值但互不引用，改封顶要前后端各改一处
          maxItems: MAX_HIGHLIGHT_BOXES - 1,
          description: `可选：同页其余命中气泡坐标列表（最多 ${MAX_HIGHLIGHT_BOXES - 1} 组），阅读器只作静态描边`,
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
        page,
        fromBeginning,
        chapter_id,
        bubble_box,
        other_boxes,
        bubble_text,
      } = (args ?? {}) as {
        source?: string
        source_id?: string
        page?: number
        fromBeginning?: boolean
        chapter_id?: string
        bubble_box?: number[]
        other_boxes?: number[][]
        bubble_text?: string
      }
      if (!source || !source_id) {
        throw new Error('参数 "source" 与 "source_id" 均为必填项。')
      }

      const targetPage = typeof page === 'number' && page >= 1 ? page : fromBeginning ? 1 : 1
      const queryObj: Record<string, string> = { page: String(targetPage) }
      if (chapter_id) {
        queryObj.chapter = chapter_id
      }
      const boxParam = serializeBubbleBox(bubble_box)
      if (boxParam) {
        queryObj.bubble_box = boxParam
      }
      const others = serializeBubbleBoxes(other_boxes)
      if (others) {
        queryObj.bubble_boxes = others
      }
      if (bubble_text) {
        queryObj.bubble_text = bubble_text
      }
      if (boxParam || bubble_text || others) {
        queryObj.highlight_bubble = '1'
      }

      await router.push({
        path: `/comic/${encodeURIComponent(source)}/${encodeURIComponent(source_id)}/read/${targetPage}`,
        query: queryObj,
      })

      return {
        success: true,
        message: `已直达漫画 ${source}/${source_id} 第 ${targetPage} 页阅读器${bubble_text ? ` 并高亮气泡：“${bubble_text}”` : ''}`,
        source,
        source_id,
        page: targetPage,
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

  // 工具 7: 收录/导入新漫画至本地书库（仅馆长权限注册）
  const importComicTool = canWrite.value
    ? useWebMCP({
        name: 'shelf_import_comic',
        description:
          '将漫画收录导入至本地书库。支持禁漫车号、哔咔画卷 ID/分享链接、以及服务器本地目录/PDF 导入；支持自动推断图源、后台离线全本预缓存、初始标签设定与收藏联动',
        inputSchema: {
          type: 'object',
          properties: {
            id: {
              type: 'string',
              description:
                '漫画车号或标识符（例如禁漫 "523607" 或 "JM523607"、哔咔 24 位 ID 或分享链接、服务器本地目录 "public/tiya-frames"）',
            },
            source_id: {
              type: 'string',
              description: '与 id 等效的漫画唯一作品标识符（若传入则优先使用）',
            },
            source: {
              type: 'string',
              enum: ['jm', 'picacg', 'local'],
              description: '可选的图源 Provider。若省略，系统将根据输入字符串格式自动智能推断',
            },
            local_path: {
              type: 'string',
              description: '若导入服务器本地已有文件夹或 PDF 文件，可显式传入本地路径',
            },
            prefetch_all: {
              type: 'boolean',
              description: '收录后是否立即在后台启动全本离线预缓存任务（默认 false）',
            },
            prefetch_covers: {
              type: 'number',
              description: '首次收录时即时预热的封面张数（默认 4）',
            },
            favorite: {
              type: 'boolean',
              description: '收录成功后是否自动加入红心喜欢（默认 false）',
            },
            tags: {
              type: 'array',
              items: { type: 'string' },
              description: '可选为收录漫画追加的初始自定义分类标签列表',
            },
            open_after: {
              type: 'boolean',
              description: '收录成功后是否自动导航跳转至该漫画的详情页（默认 false）',
            },
          },
        },
        async execute(args) {
          const {
            id,
            source_id,
            source: rawSource,
            local_path,
            prefetch_all = false,
            prefetch_covers = 4,
            favorite = false,
            tags = [],
            open_after = false,
          } = (args ?? {}) as {
            id?: string
            source_id?: string
            source?: 'jm' | 'picacg' | 'local'
            local_path?: string
            prefetch_all?: boolean
            prefetch_covers?: number
            favorite?: boolean
            tags?: string[]
            open_after?: boolean
          }

          const inputVal = (source_id || id || local_path || '').trim()
          if (!inputVal) {
            throw new Error('请提供漫画车号、作品 ID 或本地路径（id / source_id / local_path）。')
          }

          // 智能识别图源 Provider
          let finalSource: 'jm' | 'picacg' | 'local' = rawSource || 'jm'
          let finalId = inputVal

          if (!rawSource) {
            if (
              local_path ||
              inputVal.startsWith('/') ||
              inputVal.startsWith('./') ||
              inputVal.startsWith('public/')
            ) {
              finalSource = 'local'
            } else if (
              inputVal.includes('picacomic') ||
              inputVal.includes('picawang') ||
              /^[0-9a-fA-F]{24}$/.test(inputVal)
            ) {
              finalSource = 'picacg'
              // 提取 24 位 hex ID
              const hexMatch = inputVal.match(/[0-9a-fA-F]{24}/)
              if (hexMatch) {
                finalId = hexMatch[0]
              }
            } else {
              finalSource = 'jm'
            }
          }

          let importedSource: string = finalSource
          let importedSourceId = finalId
          let importedTitle = finalId
          let pageCount = 0
          let fromCache = false

          if (finalSource === 'local') {
            const res = await api.importLocalPath({ path: finalId })
            await store.load()
            importedSource = res.meta.source
            importedSourceId = res.meta.source_id
            importedTitle = res.meta.title
            pageCount = res.meta.page_count
            fromCache = false
          } else {
            const result = await store.importComic({
              id: finalId,
              source: finalSource,
              prefetch_covers: typeof prefetch_covers === 'number' ? prefetch_covers : 4,
              prefetch_all: Boolean(prefetch_all),
            })
            importedSource = result.meta.source
            importedSourceId = result.meta.source_id
            importedTitle = result.meta.title
            pageCount = result.meta.page_count
            fromCache = result.from_cache
          }

          // 后续动作 1: 标记喜欢
          if (favorite) {
            try {
              await api.setFavorite(importedSource, importedSourceId, true)
              store.setFavoriteLocal(importedSource, importedSourceId, true)
            } catch {
              // 忽略非关键错误
            }
          }

          // 后续动作 2: 追加自定义标签
          if (Array.isArray(tags) && tags.length > 0) {
            try {
              const detailRes = await api.detail(importedSource, importedSourceId)
              const mergedTags = Array.from(new Set([...(detailRes.meta.tags || []), ...tags]))
              await api.updateMetadata(importedSource, importedSourceId, { tags: mergedTags })
              await store.load()
            } catch {
              // 忽略非关键错误
            }
          }

          // 后续动作 3: 自动跳转详情页
          if (open_after) {
            await router.push({
              name: 'comic-detail',
              params: { source: importedSource, sourceId: importedSourceId },
            })
          }

          return {
            success: true,
            message: `已成功收录漫画《${importedTitle}》（${importedSource}/${importedSourceId}，共 ${pageCount} 页）`,
            comic: {
              source: importedSource,
              source_id: importedSourceId,
              title: importedTitle,
              page_count: pageCount,
              from_cache: fromCache,
              favorite: Boolean(favorite),
            },
          }
        },
      })
    : undefined

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

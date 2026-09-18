/**
 * @file useComicDetailWebMCP.ts
 * @description 漫画详情与章节子路由视口前端模型上下文协议（WebMCP）全功能工具注册组合式函数。
 *
 * 核心设计与架构定位：
 * 1. 【详情与章节操作面 (Detail & Chapter Viewport-Scoped Tools)】：
 *    在 ComicDetailView 与 ChapterView 挂载期间向浏览器 AI Agent 暴露阅读启动、单本/单话缓存、章节跳转与元数据查询工具；
 *    Agent 可直接发送结构化指令（如“缓存第 3 话”、“从第 1 页开始阅读”），无需在 DOM 中探查复杂的按钮与卡片。
 * 2. 【生命周期与作用域隔离】：
 *    离开详情或章节视口时工具随 Vue Scope 自动销毁注销。
 */

import { type ComputedRef, type ShallowRef, type Ref } from 'vue'
import { useWebMCP } from '@vueuse/core'
import type { Router } from 'vue-router'
import type { Chapter, ComicDetail } from '@/types'

/**
 * `useComicDetailWebMCP` 依赖项契约
 */
export interface UseComicDetailWebMCPOptions {
  /** 漫画来源 Provider (jm, local, picacg) */
  source: ComputedRef<string>
  /** 漫画唯一 ID / 车号 */
  sourceId: ComputedRef<string>
  /** 漫画元数据详情 Ref */
  detail: ShallowRef<ComicDetail | null>
  /** 章节列表 */
  chapters: ComputedRef<Chapter[]>
  /** 上次阅读页码 Ref */
  lastRead: Ref<number>
  /** 路由实例 */
  router: Router
  /** 全本离线预缓存方法（可选） */
  cacheAll?: () => Promise<void> | void
  /** 单话离线预缓存方法（可选） */
  cacheChapter?: (chapterId: string) => Promise<void> | void
  /** 切换红心收藏方法（可选） */
  toggleFavorite?: () => Promise<void> | void
  /** 当前锁定的章节 ID（若处于 ChapterView 章节子路由中） */
  activeChapterId?: ComputedRef<string | undefined>
}

/**
 * 在漫画详情与章节视图挂载期间注册 WebMCP 交互工具集
 */
export function useComicDetailWebMCP(options: UseComicDetailWebMCPOptions) {
  const {
    source,
    sourceId,
    detail,
    chapters,
    lastRead,
    router,
    cacheAll,
    cacheChapter,
    toggleFavorite,
    activeChapterId,
  } = options

  // 工具 1: 启动漫画阅读
  const startReadingTool = useWebMCP({
    name: 'detail_start_reading',
    description:
      '启动当前漫画的阅读器。支持从第 1 页开篇、从上次历史阅读进度继续、或精准直达指定页码',
    inputSchema: {
      type: 'object',
      properties: {
        page: {
          type: 'number',
          description: '指定的全局起始页码（从 1 开始的正整数）',
        },
        fromBeginning: {
          type: 'boolean',
          description: '是否从头开始阅读（若为 true 则忽略上次历史进度，直接从第 1 页打开）',
        },
      },
    },
    async execute(args) {
      const { page, fromBeginning } = (args ?? {}) as {
        page?: number
        fromBeginning?: boolean
      }

      let targetPage = 1
      if (typeof page === 'number' && page >= 1) {
        targetPage = page
      } else if (!fromBeginning && lastRead.value > 1) {
        targetPage = lastRead.value
      }

      const activeScope = activeChapterId?.value
      const query: Record<string, string> = { page: String(targetPage) }
      if (activeScope) {
        query.chapter = activeScope
      }

      await router.push({
        path: `/comic/${encodeURIComponent(source.value)}/${encodeURIComponent(sourceId.value)}/read/${targetPage}`,
        query,
      })

      return {
        success: true,
        message: `已为漫画《${detail.value?.meta.title || sourceId.value}》启动阅读（起始页码：第 ${targetPage} 页）`,
        targetPage,
      }
    },
  })

  // 工具 2: 触发整本漫画后台预缓存
  const cacheAllTool = useWebMCP({
    name: 'detail_cache_all_pages',
    description: '触发服务端后台将当前漫画的全本所有画页进行离线预缓存与解密',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    async execute() {
      if (typeof cacheAll === 'function') {
        await cacheAll()
        return {
          success: true,
          message: `已成功触发漫画《${detail.value?.meta.title || sourceId.value}》的全本后台离线预缓存任务`,
        }
      }
      throw new Error('当前视图不支持全本缓存操作。')
    },
  })

  // 工具 3: 触发单话后台预缓存
  const cacheChapterTool = useWebMCP({
    name: 'detail_cache_chapter',
    description: '触发服务端后台将当前漫画指定章节的所有画页进行离线预缓存与解密',
    inputSchema: {
      type: 'object',
      properties: {
        chapter_id: {
          type: 'string',
          description: '目标章节唯一标识符（如 "c1", "0"，若省略则默认缓存当前聚焦的章节）',
        },
      },
    },
    async execute(args) {
      const targetChapterId =
        (args as { chapter_id?: string })?.chapter_id || activeChapterId?.value
      if (!targetChapterId) {
        throw new Error('请指定需要缓存的章节 ID (chapter_id)。')
      }

      if (typeof cacheChapter === 'function') {
        await cacheChapter(targetChapterId)
        return {
          success: true,
          message: `已成功触发章节 "${targetChapterId}" 的后台预缓存任务`,
          chapter_id: targetChapterId,
        }
      }
      throw new Error('当前视图不支持单话缓存操作。')
    },
  })

  // 工具 4: 打开/切换至指定章节
  const openChapterTool = useWebMCP({
    name: 'detail_open_chapter',
    description: '进入当前漫画指定章节的独立子路由专注页',
    inputSchema: {
      type: 'object',
      properties: {
        chapter_id: {
          type: 'string',
          description: '目标章节唯一 ID（例如 "c1", "c2"）',
        },
      },
      required: ['chapter_id'],
    },
    async execute(args) {
      const { chapter_id } = (args ?? {}) as { chapter_id?: string }
      if (!chapter_id) {
        throw new Error('参数 "chapter_id" 为必填项。')
      }

      await router.push(`/comic/${source.value}/${sourceId.value}/chapter/${chapter_id}`)
      return {
        success: true,
        message: `已切换至章节 "${chapter_id}" 详情子路由`,
        chapter_id,
      }
    },
  })

  // 工具 5: 获取漫画详情与缓存进度概要
  const getInfoTool = useWebMCP({
    name: 'detail_get_comic_info',
    description: '获取当前漫画的完整元数据、离线缓存进度比例、全书章节目录及上次阅读记录快照',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    async execute() {
      const meta = detail.value?.meta
      if (!meta) {
        throw new Error('漫画详情元数据尚未加载完成。')
      }

      return {
        success: true,
        comic: {
          source: meta.source,
          source_id: meta.source_id,
          display_id: meta.display_id || meta.source_id,
          title: meta.title,
          authors: meta.authors,
          tags: meta.tags,
          page_count: meta.page_count,
          cached_pages: detail.value?.cached_pages || 0,
          favorite: Boolean(meta.favorite),
          last_read_page: lastRead.value,
          chapters_count: chapters.value.length,
          chapters: chapters.value.map((c) => ({
            id: c.id,
            title: c.title,
            page_count: c.page_count,
            start_page: c.start,
          })),
        },
      }
    },
  })

  // 工具 6: 切换收藏红心
  const favTool = useWebMCP({
    name: 'detail_toggle_favorite',
    description: '切换当前漫画的红心收藏（喜欢/取消喜欢）状态',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    async execute() {
      if (typeof toggleFavorite === 'function') {
        await toggleFavorite()
        return {
          success: true,
          message: `已切换漫画《${detail.value?.meta.title || sourceId.value}》的红心收藏状态（当前：${detail.value?.meta.favorite ? '已收藏' : '未收藏'}）`,
          favorite: Boolean(detail.value?.meta.favorite),
        }
      }
      return {
        success: false,
        message: '当前会话中收藏操作不可用。',
      }
    },
  })

  return {
    isSupported: startReadingTool.isSupported,
    startReadingTool,
    cacheAllTool,
    cacheChapterTool,
    openChapterTool,
    getInfoTool,
    favTool,
  }
}

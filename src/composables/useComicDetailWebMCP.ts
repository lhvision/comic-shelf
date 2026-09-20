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

import { ref, type Ref } from 'vue'
import { useWebMCP } from '@vueuse/core'
import type { Router } from 'vue-router'
import { api } from '@/api/client'
import { useAuth } from '@/composables/useAuth'
import type { Chapter, ComicDetail } from '@/types'

/**
 * `useComicDetailWebMCP` 依赖项契约
 */
export interface UseComicDetailWebMCPOptions {
  /** 漫画来源 Provider (jm, local, picacg) */
  source: Ref<string>
  /** 漫画唯一 ID / 车号 */
  sourceId: Ref<string>
  /** 漫画元数据详情 Ref */
  detail: Ref<ComicDetail | null>
  /** 章节列表 */
  chapters: Ref<Chapter[]>
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
  activeChapterId?: Ref<string | undefined>
}

import type { WebMCPComposableReturn } from '@/types'

export type UseComicDetailWebMCPReturn = WebMCPComposableReturn<
  | 'startReadingTool'
  | 'cacheAllTool'
  | 'cacheChapterTool'
  | 'openChapterTool'
  | 'getInfoTool'
  | 'favTool'
  | 'createDirectPassTool'
>

/**
 * 在漫画详情与章节子路由视口期间注册 WebMCP 全功能交互工具集
 */
export function useComicDetailWebMCP(
  options: UseComicDetailWebMCPOptions,
): UseComicDetailWebMCPReturn {
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
  const { canWrite, isDirectPass } = useAuth()

  // 单本沙箱临时受访者：彻底关停 WebMCP，避免外部自动化脚本穿透与高频抓取
  if (isDirectPass.value) {
    return {
      isSupported: ref(false),
    }
  }

  // 工具 1: 启动漫画阅读
  const startReadingTool = useWebMCP({
    name: 'detail_start_reading',
    description:
      '启动当前漫画的阅读器。支持从第 1 页开篇、从上次历史阅读进度继续、精准直达指定全局页码或跳转至指定章节开卷',
    inputSchema: {
      type: 'object',
      properties: {
        page: {
          type: 'number',
          description: '指定的全局起始页码（从 1 开始的正整数）',
        },
        chapter_id: {
          type: 'string',
          description: '可选指定跳转至特定章节的第一页开篇（如 "c1", "c2"）',
        },
        fromBeginning: {
          type: 'boolean',
          description: '是否从头开始阅读（若为 true 则忽略上次历史进度，直接从第 1 页打开）',
        },
      },
    },
    async execute(args) {
      const { page, chapter_id, fromBeginning } = (args ?? {}) as {
        page?: number
        chapter_id?: string
        fromBeginning?: boolean
      }

      let targetPage = 1
      const activeScope = chapter_id || activeChapterId?.value

      if (chapter_id) {
        const found = chapters.value.find((c) => c.id === chapter_id)
        if (found) {
          targetPage = typeof page === 'number' && page >= 1 ? found.start + page - 1 : found.start
        }
      } else if (typeof page === 'number' && page >= 1) {
        targetPage = page
      } else if (!fromBeginning && lastRead.value > 1) {
        targetPage = lastRead.value
      }

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
        message: `已为漫画《${detail.value?.meta.title || sourceId.value}》启动阅读（起始页码：第 ${targetPage} 页${activeScope ? `，章节：${activeScope}` : ''}）`,
        targetPage,
      }
    },
  })

  // 工具 2: 触发整本漫画后台预缓存（仅馆长权限注册）
  const cacheAllTool = canWrite.value
    ? useWebMCP({
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
    : undefined

  // 工具 3: 触发单话后台预缓存（仅馆长权限注册）
  const cacheChapterTool = canWrite.value
    ? useWebMCP({
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
    : undefined

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

  // 工具 6: 切换或设定收藏红心
  const favTool = useWebMCP({
    name: 'detail_toggle_favorite',
    description: '切换或显式设定当前漫画的红心收藏（喜欢/取消喜欢）状态',
    inputSchema: {
      type: 'object',
      properties: {
        favorite: {
          type: 'boolean',
          description:
            '可选显式设定收藏状态（true 设为喜欢，false 取消喜欢；若省略则自动翻转当前状态）',
        },
      },
    },
    async execute(args) {
      const desiredFav = (args as { favorite?: boolean })?.favorite
      const currentFav = Boolean(detail.value?.meta.favorite)

      if (typeof desiredFav === 'boolean' && desiredFav === currentFav) {
        return {
          success: true,
          message: `漫画《${detail.value?.meta.title || sourceId.value}》已处于${desiredFav ? '已收藏' : '未收藏'}状态`,
          favorite: currentFav,
        }
      }

      if (typeof toggleFavorite === 'function') {
        await toggleFavorite()
        const newFav = Boolean(detail.value?.meta.favorite)
        return {
          success: true,
          message: `已更新漫画《${detail.value?.meta.title || sourceId.value}》的红心收藏状态为：${newFav ? '已收藏' : '未收藏'}`,
          favorite: newFav,
        }
      }
      return {
        success: false,
        message: '当前会话中收藏操作不可用。',
      }
    },
  })

  // 工具 7: 签发单本沙箱临时直达阅读通行证（仅馆长权限注册）
  const createDirectPassTool = canWrite.value
    ? useWebMCP({
        name: 'detail_create_direct_pass',
        description:
          '为当前漫画签发单本沙箱临时直达阅读通行证（Single-Book Sandbox Direct Pass）。生成的链接携带独立单本临时令牌（temp_token），受访者只能阅读当前漫画的指定页与后续章节，无法访问书架其他私密典藏或执行任何写操作与配置修改。',
        inputSchema: {
          type: 'object',
          properties: {
            page: {
              type: 'number',
              description:
                '指定直达阅读的起始全局页码（从 1 开始的正整数，默认从第 1 页或上次阅读进度开启）',
            },
            ttl_seconds: {
              type: 'number',
              description:
                '通行证有效时长（秒），默认 7200 秒（2小时），取值范围 60 ~ 604800 秒（7天）',
            },
          },
        },
        async execute(args) {
          const { page, ttl_seconds } = (args ?? {}) as {
            page?: number
            ttl_seconds?: number
          }

          let targetPage = 1
          if (typeof page === 'number' && page >= 1) {
            targetPage = Math.floor(page)
          } else if (lastRead.value > 1) {
            targetPage = lastRead.value
          }
          const totalPages = detail.value?.meta.page_count ?? 1
          targetPage = Math.min(Math.max(1, targetPage), Math.max(1, totalPages))

          const validTtl =
            typeof ttl_seconds === 'number' && ttl_seconds > 0
              ? Math.min(Math.max(Math.floor(ttl_seconds), 60), 604800)
              : 7200

          const res = await api.createDirectPass({
            source: source.value,
            source_id: sourceId.value,
            page_index: targetPage,
            ttl_seconds: validTtl,
          })

          const origin =
            typeof window !== 'undefined' && window.location?.origin ? window.location.origin : ''
          const fullUrl = origin ? `${origin}${res.direct_url}` : res.direct_url
          const hours = Math.round((res.expires_in / 3600) * 10) / 10

          return {
            success: true,
            message: `已为漫画《${detail.value?.meta.title || sourceId.value}》成功签发单本沙箱直达链接（有效时长：${hours} 小时，起始页码：第 ${res.page_index} 页）`,
            token: res.token,
            direct_url: res.direct_url,
            full_url: fullUrl,
            page_index: res.page_index,
            expires_at: res.expires_at,
            expires_in: res.expires_in,
          }
        },
      })
    : undefined

  return {
    isSupported: startReadingTool.isSupported,
    startReadingTool,
    cacheAllTool,
    cacheChapterTool,
    openChapterTool,
    getInfoTool,
    favTool,
    createDirectPassTool,
  }
}

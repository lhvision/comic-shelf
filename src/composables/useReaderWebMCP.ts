/**
 * @file useReaderWebMCP.ts
 * @description 阅读器视口前端模型上下文协议（WebMCP）全功能声明式工具注册组合式函数。
 *
 * 核心设计与架构定位：
 * 1. 【操作面与生命周期绑定 (Viewport-Scoped Tools)】：
 *    借助 VueUse 15 `useWebMCP` 原生接入 Chrome 浏览器级 `document.modelContext.registerTool()` 规范；
 *    仅在 ReaderView 挂载存活期间向浏览器 Agent 暴露操作工具（跳页、翻页、切模式、缩放适配、自动翻页、高亮气泡、跨章导航、喜欢标记），
 *    组件卸载时随 Vue Scope 自动销毁注销，杜绝跨页面非法调用。
 * 2. 【安全静默降级 (Graceful Degradation)】：
 *    若宿主浏览器未开启 WebMCP 支持，底层自动安全空跑（No-op），零控制台警告，零副作用。
 */

import { type ComputedRef, type Ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { useWebMCP } from '@vueuse/core'
import type { FitMode, ReaderMode, ReaderSettings } from '@/composables/useReaderSettings'

/**
 * `useReaderWebMCP` 依赖项契约
 */
export interface UseReaderWebMCPOptions {
  /** 当前展示的全局/本地页码 Ref */
  currentPage: Ref<number>
  /** 漫画总页数 */
  pageCount: ComputedRef<number>
  /** 阅读器设置对象（响应式） */
  settings: ReaderSettings
  /** 页面跳转方法 */
  goToPage: (page: number) => void
  /** 上一屏/上一组分屏翻页方法 */
  prevGroup: () => void
  /** 下一屏/下一组分屏翻页方法 */
  nextGroup: () => void
  /** 跨章节切入下一话方法（可选） */
  goNextChapter?: () => void
  /** 跨章节切入上一话方法（可选） */
  goPrevChapter?: () => void
  /** 切换漫画红心收藏状态方法（可选） */
  toggleFavorite?: () => void
  /** 漫画标题（可选，增强 Prompt 理解） */
  title?: ComputedRef<string>
  /** 当前是否处于喜欢状态（可选） */
  isFavorite?: ComputedRef<boolean>
  /** 路由实例（用于气泡定位参数注入） */
  router?: Router
  /** 当前路由对象（用于提取已有 Query） */
  route?: RouteLocationNormalizedLoaded
}

/**
 * 在阅读器挂载期间注册 WebMCP 浏览器端交互全功能工具集
 */
export function useReaderWebMCP(options: UseReaderWebMCPOptions) {
  const {
    currentPage,
    pageCount,
    settings,
    goToPage,
    prevGroup,
    nextGroup,
    goNextChapter,
    goPrevChapter,
    toggleFavorite,
    title,
    isFavorite,
    router,
    route,
  } = options

  // 工具 1: 跳转指定页码
  const jumpTool = useWebMCP({
    name: 'reader_jump_to_page',
    description: '在当前打开的漫画阅读器中，精准跳转至指定的 1-based 全局页码',
    inputSchema: {
      type: 'object',
      properties: {
        page: {
          type: 'number',
          description: '目标跳转页码（从 1 开始的有效正整数）',
        },
      },
      required: ['page'],
    },
    async execute(args) {
      const target = Number((args as { page?: number }).page)
      if (!Number.isFinite(target) || target < 1) {
        throw new Error(`无效的页码参数：${target}`)
      }
      goToPage(target)
      return {
        success: true,
        message: `阅读器已跳转至第 ${target} 页（全书共 ${pageCount.value} 页）`,
        currentPage: target,
      }
    },
  })

  // 工具 2: 步进翻页
  const turnTool = useWebMCP({
    name: 'reader_turn_page',
    description: '在阅读器中向前或向后步进翻页（支持多页并排与分屏模式）',
    inputSchema: {
      type: 'object',
      properties: {
        direction: {
          type: 'string',
          enum: ['next', 'prev'],
          description: '翻页方向：next 为向后翻下一页/下一屏，prev 为向前翻上一页/上一屏',
        },
      },
      required: ['direction'],
    },
    async execute(args) {
      const dir = (args as { direction?: string }).direction
      if (dir === 'next') {
        nextGroup()
      } else if (dir === 'prev') {
        prevGroup()
      } else {
        throw new Error(`不支持的翻页方向参数：${dir}`)
      }
      return {
        success: true,
        message: `已向${dir === 'next' ? '后' : '前'}翻页（当前处于第 ${currentPage.value} 页）`,
        currentPage: currentPage.value,
      }
    },
  })

  // 工具 3: 切换阅读排版模式与分屏方向
  const modeTool = useWebMCP({
    name: 'reader_switch_mode',
    description:
      '动态配置与切换阅读器的排版布局。支持设置排版模式（条漫/单页/横向）、单屏分屏画页数（1/2/4页）以及翻页方向（从左往右/从右往左日漫模式）',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['vertical-continuous', 'vertical-paged', 'horizontal'],
          description:
            '排版模式：vertical-continuous（竖向连续条漫瀑布流）、vertical-paged（竖向单页吸附滚动）、horizontal（横向切页排版）',
        },
        pagesPerView: {
          type: 'number',
          enum: [1, 2, 4],
          description:
            '单屏展示画页数：1（单页阅读）、2（双页并排/日漫展开）、4（四连页/宽屏画集）',
        },
        direction: {
          type: 'string',
          enum: ['ltr', 'rtl'],
          description: '横向翻页方向：ltr（从左向右/常规现代）、rtl（从右向左/日漫传统）',
        },
      },
    },
    async execute(args) {
      const { mode, pagesPerView, direction } = (args ?? {}) as {
        mode?: ReaderMode
        pagesPerView?: 1 | 2 | 4
        direction?: 'ltr' | 'rtl'
      }

      if (!mode && pagesPerView === undefined && !direction) {
        throw new Error(
          '请至少指定 mode(排版模式)、pagesPerView(单屏页数) 或 direction(翻页方向) 中的一个参数。',
        )
      }

      if (mode) {
        if (mode === 'vertical-continuous' || mode === 'vertical-paged' || mode === 'horizontal') {
          settings.mode = mode
        } else {
          throw new Error(`不支持的阅读器排版模式：${String(mode)}`)
        }
      }

      if (pagesPerView !== undefined) {
        if (pagesPerView === 1 || pagesPerView === 2 || pagesPerView === 4) {
          settings.pagesPerView = pagesPerView
        } else {
          throw new Error(`不支持的单屏页数：${String(pagesPerView)}（仅支持 1、2、4）`)
        }
      }

      if (direction) {
        if (direction === 'ltr' || direction === 'rtl') {
          settings.direction = direction
        } else {
          throw new Error(`不支持的翻页方向：${String(direction)}（仅支持 ltr、rtl）`)
        }
      }

      return {
        success: true,
        message: `已更新阅读器排版设置（模式：${settings.mode}，分屏：${settings.pagesPerView}页，方向：${settings.direction}）`,
        currentMode: settings.mode,
        pagesPerView: settings.pagesPerView,
        direction: settings.direction,
      }
    },
  })

  // 工具 4: 切换画面缩放适应模式 (fit)
  const fitTool = useWebMCP({
    name: 'reader_switch_fit',
    description:
      '切换画页在阅读视口中的缩放适配策略：width（适应视口宽度）或 height（适应视口高度）',
    inputSchema: {
      type: 'object',
      properties: {
        fit: {
          type: 'string',
          enum: ['width', 'height'],
          description: '目标画面缩放适配策略',
        },
      },
      required: ['fit'],
    },
    async execute(args) {
      const targetFit = (args as { fit?: FitMode }).fit
      if (targetFit === 'width' || targetFit === 'height') {
        settings.fit = targetFit
        return {
          success: true,
          message: `已将画面缩放适配策略切换为：${targetFit}`,
          currentFit: targetFit,
        }
      }
      throw new Error(`不支持的缩放适配策略：${targetFit}`)
    },
  })

  // 工具 5: 配置与切换自动翻页 (auto turn)
  const autoTurnTool = useWebMCP({
    name: 'reader_toggle_auto_turn',
    description: '开启、关闭自动翻页功能，或调节自动翻页倒计时秒数间隔',
    inputSchema: {
      type: 'object',
      properties: {
        enable: {
          type: 'boolean',
          description: '是否开启自动翻页（true 开启，false 关闭，省略则切换当前状态）',
        },
        interval: {
          type: 'number',
          description: '翻页倒计时秒数（例如 5、10、15、30 秒）',
        },
      },
    },
    async execute(args) {
      const { enable, interval } = (args ?? {}) as { enable?: boolean; interval?: number }
      if (typeof interval === 'number' && interval >= 1) {
        settings.autoTurnInterval = Math.round(interval)
      }
      if (typeof enable === 'boolean') {
        settings.autoTurn = enable
      } else {
        settings.autoTurn = !settings.autoTurn
      }

      return {
        success: true,
        message: `自动翻页已${settings.autoTurn ? '开启' : '关闭'}（翻页间隔：${settings.autoTurnInterval} 秒）`,
        autoTurn: settings.autoTurn,
        interval: settings.autoTurnInterval,
      }
    },
  })

  // 工具 6: 切换收藏红心标记
  const favTool = useWebMCP({
    name: 'reader_toggle_favorite',
    description: '在阅读器中快速切换当前漫画的红心收藏状态',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    async execute() {
      if (typeof toggleFavorite === 'function') {
        toggleFavorite()
        return {
          success: true,
          message: `已切换漫画《${title?.value ?? '当前漫画'}》的红心收藏状态`,
          favorite: isFavorite ? isFavorite.value : undefined,
        }
      }
      return {
        success: false,
        message: '当前阅读会话中收藏操作不可用。',
      }
    },
  })

  // 工具 7: 定位并呼吸高亮漫画对白气泡
  const locateBubbleTool = useWebMCP({
    name: 'reader_locate_bubble',
    description:
      '定位画页并以朱砂色呼吸线框高亮指定的对白气泡框（常用于台词搜索后一键直达分镜位置）',
    inputSchema: {
      type: 'object',
      properties: {
        page: {
          type: 'number',
          description: '气泡所在的 1-based 画页页码',
        },
        box: {
          type: 'array',
          items: { type: 'number' },
          description: '气泡在画页中的归一化边界坐标 [ymin, xmin, ymax, xmax]（取值范围 0~1）',
        },
        text: {
          type: 'string',
          description: '气泡内的对白台词文本片段',
        },
      },
      required: ['page'],
    },
    async execute(args) {
      const { page, box, text } = (args ?? {}) as {
        page?: number
        box?: number[]
        text?: string
      }
      const targetPage = Number(page)
      if (!Number.isFinite(targetPage) || targetPage < 1) {
        throw new Error(`无效的页码参数：${page}`)
      }
      goToPage(targetPage)

      if (router && route) {
        const boxStr = Array.isArray(box) && box.length === 4 ? box.join(',') : undefined
        await router.replace({
          query: {
            ...route.query,
            page: String(targetPage),
            ...(boxStr ? { bubble_box: boxStr } : {}),
            ...(text ? { bubble_text: text } : {}),
            highlight_bubble: '1',
          },
        })
      }

      return {
        success: true,
        message: `已聚焦至第 ${targetPage} 页的气泡分镜${text ? `：“${text}”` : ''}`,
        page: targetPage,
        box,
        text,
      }
    },
  })

  // 工具 8: 跨章节导航
  const jumpChapterTool = useWebMCP({
    name: 'reader_jump_chapter',
    description: '在多章节漫画中跨话切换上一话或下一话',
    inputSchema: {
      type: 'object',
      properties: {
        direction: {
          type: 'string',
          enum: ['next', 'prev'],
          description: '章节跳转方向：next 为下一话，prev 为上一话',
        },
      },
      required: ['direction'],
    },
    async execute(args) {
      const { direction } = (args ?? {}) as { direction?: string }
      if (direction === 'next') {
        if (typeof goNextChapter === 'function') {
          goNextChapter()
          return { success: true, message: '已跳转至下一话' }
        }
      } else if (direction === 'prev') {
        if (typeof goPrevChapter === 'function') {
          goPrevChapter()
          return { success: true, message: '已跳转至上一话' }
        }
      }
      throw new Error(`无法跨话跳转：当前没有可用的${direction === 'next' ? '下一话' : '上一话'}。`)
    },
  })

  return {
    isSupported: jumpTool.isSupported,
    jumpTool,
    turnTool,
    modeTool,
    fitTool,
    autoTurnTool,
    favTool,
    locateBubbleTool,
    jumpChapterTool,
  }
}

import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'
import { useCoverTransition } from '@/composables/useCoverTransition'
import { withResolvers } from '@/utils/promise'

import { useShelfState } from '@/composables/useShelfState'
import { useAuth } from '@/composables/useAuth'

let hasPreScrolled = false
let isPopStateNavigation = false

if (typeof window !== 'undefined') {
  window.addEventListener('popstate', () => {
    isPopStateNavigation = true
  })
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'library',
      component: () => import('@/views/LibraryView.vue'),
      meta: { title: '书库', rank: 1 },
    },
    {
      path: '/comic/:source/:sourceId',
      name: 'comic-detail',
      component: () => import('@/views/ComicDetailView.vue'),
      meta: { title: '本子详情', rank: 2 },
    },
    {
      path: '/create',
      name: 'create-comic',
      component: () => import('@/views/CreateComicView.vue'),
      meta: { title: '自建图集工坊', rank: 2 },
    },
    {
      path: '/discovery',
      name: 'discovery',
      component: () => import('@/views/DiscoveryView.vue'),
      meta: { title: '官方发现与排行', rank: 1 },
    },
    {
      path: '/comic/:source/:sourceId/read/:page?',
      name: 'reader',
      component: () => import('@/views/ReaderView.vue'),
      meta: { title: '阅读', rank: 4 },
    },
    {
      path: '/comic/:source/:sourceId/chapter/:chapterId',
      name: 'comic-chapter',
      component: () => import('@/views/ChapterView.vue'),
      meta: { title: '章节', rank: 3 },
    },
    {
      path: '/vapor-canary',
      name: 'vapor-canary',
      component: () => import('@/views/VaporCanaryView.vue'),
      meta: { title: 'Vapor Mode 基准沙盒', rank: 2 },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
  scrollBehavior(to, from, savedPosition) {
    // 若返回书架页面，优先还原书架全景上下文记忆中的滚动坐标（Shelf Context Memory）
    if (to.name === 'library') {
      const { shelfScrollY } = useShelfState()
      if (shelfScrollY.value > 0) {
        return { top: shelfScrollY.value, behavior: 'instant' }
      }
    }
    if (savedPosition) {
      return savedPosition
    }
    // 同页面仅 query 或 hash 变更（如书架分类胶囊、筛选或排序切换），保持视口坐标，禁止粗暴滚顶
    if (to.path === from.path) {
      return false
    }
    // 若前进推进已在 View Transition 捕获缝隙中瞬时归零，直接放行，0 几何属性读取与 0 强排
    if (hasPreScrolled) {
      hasPreScrolled = false
      return false
    }
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const { isDirectPass, directPassComic } = useAuth()
  if (isDirectPass.value && directPassComic.value) {
    const { source, sourceId } = directPassComic.value
    // 单本沙箱模式：严格锁定读者仅能访问本作（详情、阅读器、章节子路由）
    const isTargetComic =
      (to.name === 'comic-detail' || to.name === 'reader' || to.name === 'comic-chapter') &&
      to.params.source === source &&
      to.params.sourceId === sourceId
    if (!isTargetComic) {
      return `/comic/${source}/${sourceId}`
    }
  }
})

router.beforeResolve(async (to, from) => {
  if (typeof document === 'undefined' || !document.startViewTransition) return true
  if (to.path === from.path) return true

  // 同在阅读器内部翻页 / 章节切换 / 滚动切换页码，不触发全屏路由视图过渡（避免快速翻页中断碰撞）
  if (to.name === 'reader' && from.name === 'reader') {
    return true
  }

  if (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) {
    return true
  }

  const fromRank = Number(from.meta?.rank ?? 1)
  const toRank = Number(to.meta?.rank ?? 1)
  const direction = toRank >= fromRank ? 'forward' : 'backward'

  const { promise, resolve } = withResolvers<void>()
  let resolved = false
  const safeResolve = () => {
    if (!resolved) {
      resolved = true
      resolve()
    }
  }

  // 严格超时保护（Zero-Deadlock Guard）：
  // 在 WebKit / iPadOS 等环境下，当视图快照阻塞或过渡被抢占时，350ms 严格超时放行路由，彻底杜绝路由卡死
  const timeoutId = setTimeout(safeResolve, 350)

  let updateExecuted = false
  const performUpdate = async () => {
    if (updateExecuted) return
    updateExecuted = true
    clearTimeout(timeoutId)

    // 捕获间隙瞬时重置（In-Flight Pre-Capture Scroll）：
    // 当旧视图快照已由浏览器离屏捕获（被 GPU 冻结在屏幕上）、新视图尚未挂载时，
    // 前进推进瞬时将视口归零：
    // 1. 旧页面冻结快照遮挡住视口变动，读者视觉无跳动；
    // 2. 新视图直接挂载在 (0, 0)，View Transition 截取 ::view-transition-new(root) 处于真实顶端；
    // 3. 彻底根除 Vue Router 在微任务中调用 scrollToPosition 强排新视图（消除 134~209ms 阻塞）。
    if (direction === 'forward' && !isPopStateNavigation) {
      hasPreScrolled = true
      if (typeof window !== 'undefined') {
        window.scrollTo({ top: 0, behavior: 'instant' })
      }
    }
    safeResolve()
    await nextTick()
  }

  try {
    const doc = document as unknown as {
      startViewTransition: (
        cbOrOpt: (() => Promise<void>) | { update: () => Promise<void>; types: string[] },
      ) => {
        ready?: Promise<void>
        finished?: Promise<void>
        updateCallbackDone?: Promise<void>
      }
    }
    let transition
    try {
      transition = doc.startViewTransition({
        update: performUpdate,
        types: [direction],
      })
    } catch {
      transition = doc.startViewTransition(performUpdate)
    }

    transition?.ready?.catch(() => {})
    void transition?.updateCallbackDone?.finally(performUpdate).catch(() => {})
    void transition?.finished?.finally(safeResolve).catch(() => {})
  } catch {
    void performUpdate()
  }

  return promise
})

const { clearActiveCover } = useCoverTransition()

router.afterEach((to) => {
  // 确保单次推进生命周期结束后重置标记，杜绝状态跨路由泄露
  hasPreScrolled = false
  isPopStateNavigation = false

  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · 纸间` : '纸间 · Paper Room'

  // 在单次过渡完成后清理共享封面标记
  setTimeout(() => {
    clearActiveCover()
  }, 400)
})

router.onError(() => {
  hasPreScrolled = false
  isPopStateNavigation = false
})

export default router

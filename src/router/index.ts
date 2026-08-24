import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'
import { useCoverTransition } from '@/composables/useCoverTransition'

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
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
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

  return new Promise<void>((resolve) => {
    let resolved = false
    const performUpdate = async () => {
      if (!resolved) {
        resolved = true
        resolve()
      }
      await nextTick()
    }

    try {
      const doc = document as unknown as {
        startViewTransition: (opt: { update: () => Promise<void>; types: string[] }) => {
          ready?: Promise<void>
          finished?: Promise<void>
          updateCallbackDone?: Promise<void>
        }
      }
      const transition = doc.startViewTransition({
        update: performUpdate,
        types: [direction],
      })
      transition?.ready?.catch(() => {})
      transition?.finished?.catch(() => {})
      transition?.updateCallbackDone?.catch(() => {})
    } catch {
      try {
        const transition = document.startViewTransition(performUpdate) as unknown as {
          ready?: Promise<void>
          finished?: Promise<void>
          updateCallbackDone?: Promise<void>
        }
        transition?.ready?.catch(() => {})
        transition?.finished?.catch(() => {})
        transition?.updateCallbackDone?.catch(() => {})
      } catch {
        if (!resolved) {
          resolved = true
          resolve()
        }
      }
    }
  })
})

const { clearActiveCover } = useCoverTransition()

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · 纸间` : '纸间 · Paper Room'

  // 在单次过渡完成后清理共享封面标记
  setTimeout(() => {
    clearActiveCover()
  }, 400)
})

export default router

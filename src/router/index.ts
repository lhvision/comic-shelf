import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'library',
      component: () => import('@/views/LibraryView.vue'),
      meta: { title: '书库' },
    },
    {
      path: '/comic/:source/:sourceId',
      name: 'comic-detail',
      component: () => import('@/views/ComicDetailView.vue'),
      meta: { title: '本子详情' },
    },
    {
      path: '/comic/:source/:sourceId/read/:page?',
      name: 'reader',
      component: () => import('@/views/ReaderView.vue'),
      meta: { title: '阅读' },
    },
    {
      path: '/comic/:source/:sourceId/chapter/:chapterId',
      name: 'comic-chapter',
      component: () => import('@/views/ChapterView.vue'),
      meta: { title: '章节' },
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

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · 纸间` : '纸间 · Paper Room'
})

export default router

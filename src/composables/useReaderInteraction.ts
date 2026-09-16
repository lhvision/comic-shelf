/**
 * @file useReaderInteraction.ts
 * @description 阅读器用户交互状态机调度（聚合键盘快捷键、滚轮映射、自动翻页步进与排版自适应）。
 *
 * 遵循 docs/agents/frontend.md 规范：
 * - 纯领域编排组合式函数；
 * - 接收子状态机契约对象，大幅压缩视图层样板解构。
 */

import { nextTick, ref, watch, type Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { useTimeoutFn } from '@vueuse/core'
import { useReaderKeyboard } from '@/composables/useReaderKeyboard'
import { useReaderSync } from '@/composables/useReaderSync'
import type { useReaderSettings } from '@/composables/useReaderSettings'
import type { useReaderPaging } from '@/composables/useReaderPaging'
import type { useReaderChrome } from '@/composables/useReaderChrome'
import type { useAutoTurn } from '@/composables/useAutoTurn'
import type { useReaderNavigation } from '@/composables/useReaderNavigation'
import type { useReaderData } from '@/composables/useReaderData'
import type { useReaderBubble } from '@/composables/useReaderBubble'

export interface UseReaderInteractionOptions {
  userInteracted: Ref<boolean>
  currentPage: Ref<number>
  currentGroupIndex: Ref<number>
  settingsOpen: Ref<boolean>
  filmstripOpen?: Ref<boolean>
  toggleFilmstrip?: () => void
  reducedMotion: Ref<boolean>
  route: RouteLocationNormalizedLoaded
  settings: ReturnType<typeof useReaderSettings>
  bubble: ReturnType<typeof useReaderBubble>
  data: ReturnType<typeof useReaderData>
  paging: ReturnType<typeof useReaderPaging>
  chrome: ReturnType<typeof useReaderChrome>
  navigation: ReturnType<typeof useReaderNavigation>
  autoTurn: ReturnType<typeof useAutoTurn>
}

export function useReaderInteraction(options: UseReaderInteractionOptions) {
  const {
    userInteracted,
    currentPage,
    currentGroupIndex,
    settingsOpen,
    filmstripOpen,
    toggleFilmstrip,
    reducedMotion,
    route,
    settings: { settings, clearActiveComic, applyComicPreferences },
    bubble: { targetBubble, targetPage, dismissBubble },
    data: { detail, loading, source, sourceId, scopeId, backToDetail, lastRead },
    paging: { scopedPages, total, clampToScope, groupIndexForPage },
    chrome: { toggleChrome, showChromeTemporarily, scheduleChromeHide },
    navigation: {
      scrollToGroup,
      recalibrateTargetOffset,
      goToPage: navGoToPage,
      prevGroup: navPrevGroup,
      nextGroup: navNextGroup,
      advanceAutoTurn: navAdvanceAutoTurn,
      onScroll,
      onWheel,
      preloadAround,
      goNextChapter: navGoNextChapter,
      goPrevChapter: navGoPrevChapter,
      lockProgrammaticScroll,
      unlockProgrammaticScroll,
    },
    autoTurn: { resetAutoTurnCountdown },
  } = options

  /**
   * 记录初次载入或显式跳转的目标锚点页码与分组。
   * 仅用于在用户未交互前，若视口上方离屏图片异步解码撑高时精准微调，绝不跟随滚动探测漂移。
   */
  const targetAnchorPage = ref<number | null>(null)
  const targetAnchorGroupIndex = ref<number | null>(null)
  const { start: startAnchorExpiry } = useTimeoutFn(
    () => {
      targetAnchorPage.value = null
      targetAnchorGroupIndex.value = null
    },
    4000,
    { immediate: false },
  )

  async function initReaderView() {
    userInteracted.value = false
    const initial =
      targetPage.value && targetPage.value > 0
        ? targetPage.value
        : lastRead.value || scopedPages.value[0] || 1
    currentPage.value = clampToScope(initial)
    currentGroupIndex.value = groupIndexForPage(currentPage.value)
    targetAnchorPage.value = currentPage.value
    targetAnchorGroupIndex.value = currentGroupIndex.value
    startAnchorExpiry()

    await nextTick()
    scrollToGroup(currentGroupIndex.value, 'instant')
    scheduleChromeHide()
    void preloadAround(currentPage.value)
    resetAutoTurnCountdown()
  }

  function advanceAutoTurn() {
    navAdvanceAutoTurn(reducedMotion.value)
  }

  function onPageReady(page: number) {
    // 仅在用户未曾交互、处于连续模式、锚点未过期、且就绪页码严格位于当前视口锚点上方时执行微调
    // 下方画页无论如何加载排版，绝对不会改变上方锚点的 offsetTop，杜绝正反馈自激翻页
    if (
      !userInteracted.value &&
      settings.mode === 'vertical-continuous' &&
      targetAnchorGroupIndex.value !== null &&
      targetAnchorPage.value !== null &&
      page < targetAnchorPage.value &&
      targetAnchorGroupIndex.value === currentGroupIndex.value
    ) {
      recalibrateTargetOffset(targetAnchorGroupIndex.value)
    }
  }

  function onViewportWheel(event: WheelEvent) {
    onUserInteract()
    onWheel(event)
  }

  function onUserInteract() {
    userInteracted.value = true
    targetAnchorGroupIndex.value = null
    targetAnchorPage.value = null
    resetAutoTurnCountdown()
    unlockProgrammaticScroll()
  }

  function prevGroup(behavior: ScrollBehavior = 'smooth') {
    onUserInteract()
    navPrevGroup(behavior)
  }

  function nextGroup(behavior: ScrollBehavior = 'smooth') {
    onUserInteract()
    navNextGroup(behavior)
  }

  function goToPage(page: number, behavior: ScrollBehavior = 'smooth') {
    onUserInteract()
    navGoToPage(page, behavior)
  }

  function goToGroup(groupIndex: number, behavior: ScrollBehavior = 'smooth') {
    onUserInteract()
    options.navigation.goToGroup(groupIndex, behavior)
  }

  function goNextChapter() {
    onUserInteract()
    navGoNextChapter()
  }

  function goPrevChapter() {
    onUserInteract()
    navGoPrevChapter()
  }

  function onContainerScroll() {
    onScroll()
  }

  function onReaderClick(event: MouseEvent) {
    if (event.button !== 0) {
      return
    }
    const target = event.target as HTMLElement | null
    if (target?.closest('button, a, input, select, textarea, [role="button"]')) {
      return
    }
    if (window.getSelection()?.toString()) {
      return
    }
    if (filmstripOpen?.value) {
      filmstripOpen.value = false
      return
    }
    toggleChrome()
  }

  function onSelectChapter(id: string) {
    const c = detail.value?.meta.chapters?.find((item) => item.id === id)
    if (c) {
      options.navigation.setScope(c.id, c.start)
      goToPage(c.start, 'smooth')
    }
  }

  useReaderSync({
    source,
    sourceId,
    detail,
    currentPage,
    lastRead,
    clearActiveComic,
    applyComicPreferences,
    preloadAround,
  })

  const { toggleFullscreen } = useReaderKeyboard({
    settingsOpen,
    filmstripOpen,
    toggleFilmstrip,
    settings,
    total,
    goToPage,
    prevGroup,
    nextGroup,
    goNextChapter,
    goPrevChapter,
    backToDetail,
    onUserInteract,
    onKeyRelease: () => lockProgrammaticScroll(380),
  })

  watch(
    () => [route.params.page, route.query.page],
    () => {
      if (loading.value) return
      const page = targetPage.value ?? lastRead.value ?? scopedPages.value[0] ?? 1
      const pages = scopedPages.value
      if (!Number.isFinite(page) || pages.length === 0) return
      if (page < pages[0]! || page > pages[pages.length - 1]!) return
      if (page === currentPage.value) return
      goToPage(page, 'smooth')
    },
  )

  watch(
    () => `${settings.mode}|${settings.pagesPerView}|${settings.direction}`,
    async () => {
      currentGroupIndex.value = groupIndexForPage(currentPage.value)
      await nextTick()
      scrollToGroup(currentGroupIndex.value, 'instant')
      showChromeTemporarily()
      resetAutoTurnCountdown()
    },
  )

  watch(
    () => scopeId.value,
    async () => {
      if (!detail.value) return
      const clamped = clampToScope(currentPage.value)
      if (clamped !== currentPage.value) currentPage.value = clamped
      currentGroupIndex.value = groupIndexForPage(currentPage.value)
      await nextTick()
      scrollToGroup(currentGroupIndex.value, 'instant')
      showChromeTemporarily()
      resetAutoTurnCountdown()
    },
  )

  watch(currentPage, (page) => {
    if (targetBubble.value && targetBubble.value.page !== page) {
      dismissBubble()
    }
  })

  return {
    initReaderView,
    advanceAutoTurn,
    onPageReady,
    onViewportWheel,
    onUserInteract,
    onContainerScroll,
    onReaderClick,
    onSelectChapter,
    toggleFullscreen,
    prevGroup,
    nextGroup,
    goToPage,
    goToGroup,
    goNextChapter,
    goPrevChapter,
  }
}

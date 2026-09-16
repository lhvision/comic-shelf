/**
 * @file useReaderInteraction.ts
 * @description 阅读器用户交互状态机调度（聚合键盘快捷键、滚轮映射、自动翻页步进与排版自适应）。
 *
 * 遵循 docs/agents/frontend.md 规范：
 * - 纯领域编排组合式函数；
 * - 接收子状态机契约对象，大幅压缩视图层样板解构。
 */

import { nextTick, watch, type Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
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
      goToPage,
      prevGroup,
      nextGroup,
      advanceAutoTurn: navAdvanceAutoTurn,
      onScroll,
      onWheel,
      preloadAround,
      goNextChapter,
      goPrevChapter,
      unlockProgrammaticScroll,
    },
    autoTurn: { resetAutoTurnCountdown },
  } = options

  async function initReaderView() {
    userInteracted.value = false
    const initial =
      targetPage.value && targetPage.value > 0
        ? targetPage.value
        : lastRead.value || scopedPages.value[0] || 1
    currentPage.value = clampToScope(initial)
    currentGroupIndex.value = groupIndexForPage(currentPage.value)

    await nextTick()
    scrollToGroup(currentGroupIndex.value, 'instant')
    scheduleChromeHide()
    void preloadAround(currentPage.value)
    resetAutoTurnCountdown()
  }

  function advanceAutoTurn() {
    navAdvanceAutoTurn(reducedMotion.value)
  }

  function onPageReady(_page: number) {
    if (!userInteracted.value && settings.mode === 'vertical-continuous') {
      recalibrateTargetOffset(currentGroupIndex.value)
    }
  }

  function onViewportWheel(event: WheelEvent) {
    userInteracted.value = true
    resetAutoTurnCountdown()
    onWheel(event)
  }

  function onUserInteract() {
    userInteracted.value = true
    resetAutoTurnCountdown()
    unlockProgrammaticScroll()
  }

  function onContainerScroll() {
    onScroll()
  }

  function onReaderClick(event: MouseEvent) {
    const target = event.target as HTMLElement | null
    if (target?.closest('button, a, input, select, textarea, [role="button"]')) {
      return
    }
    if (window.getSelection()?.toString()) {
      return
    }
    toggleChrome()
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
    settings,
    total,
    goToPage,
    prevGroup,
    nextGroup,
    goNextChapter,
    goPrevChapter,
    backToDetail,
    onUserInteract,
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
    toggleFullscreen,
  }
}

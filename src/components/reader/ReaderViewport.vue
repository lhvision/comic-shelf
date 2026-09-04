<script setup lang="ts">
/**
 * @file ReaderViewport.vue
 * @description 阅读器画卷视口组件（承载纵向连续、纵向翻页、横向翻页三种排版模式与分屏画页渲染）。
 *
 * 核心职责：
 * 1. 物理滚动容器（`<main class="reader-scroll">`）承载与 DOM 节点挂载；
 * 2. 多屏分组（`orderedGroups`）与双联页（Spread）排版循环渲染；
 * 3. 单页图片（`ComicPageImage`）自适应装订与页脚页码指示；
 * 4. 结尾卡片（`ReaderEndCard`）在横向 RTL 日漫模式与常规模式下的分发；
 * 5. 抛出滚动、滚轮、鼠标移动与视图点击等高频视口交互事件。
 */

import { ref } from 'vue'
import { pageFileUrl } from '@/api/client'
import ComicPageImage from '@/components/ComicPageImage.vue'
import ReaderEndCard from '@/components/reader/ReaderEndCard.vue'
import type { ReaderSettings } from '@/composables/useReaderSettings'
import type { LibrarySummary } from '@/types'

/**
 * 分屏页码分组定义
 */
export interface OrderedGroup {
  /** 当前分屏包含的全局页码列表 */
  pages: number[]
  /** 分屏分组原始索引（0-based） */
  index: number
}

/**
 * `ReaderViewport` 组件 Props 契约
 */
export interface ReaderViewportProps {
  /** 阅读器设置（排版模式、适应宽度/高度、每屏页数等） */
  settings: ReaderSettings
  /** 漫画数据源 Provider 名称 */
  source: string
  /** 漫画唯一 ID */
  sourceId: string
  /** 排序后的分屏分组列表（RTL 模式下已倒序） */
  orderedGroups: OrderedGroup[]
  /** 是否展示卷末完结卡片 */
  showEndCard: boolean
  /** 是否处于横向 RTL 日漫翻页模式 */
  rtlHorizontal: boolean
  /** 随机看板插画序号或路径（保证整本书加载占位一致） */
  loadingVariant: string | number
  /** 全局页码转分章本地页码函数 */
  toLocalPage: (page: number) => number
  /** 卷末接卷推荐藏书列表 */
  recommendations?: LibrarySummary[]
}

defineProps<ReaderViewportProps>()

defineEmits<{
  /** 容器滚动事件 */
  scroll: [event: Event]
  /** 容器滚轮事件 */
  wheel: [event: WheelEvent]
  /** 鼠标滑移事件（唤醒顶栏） */
  mousemove: [event: MouseEvent]
  /** 视口点击事件（切换顶栏显隐） */
  readerClick: [event: MouseEvent]
  /** 用户主动交互（触屏/按压） */
  userInteract: []
  /** 单页图片加载就绪事件（用于连续模式微调定位） */
  pageReady: [page: number]
  /** 点击完结卡片返回详情页 */
  backToDetail: []
  /** 返回书架首页 */
  backToShelf: []
  /** 直接开读推荐作品 */
  selectComic: [source: string, sourceId: string]
  /** 查看推荐作品详情 */
  openComicDetail: [source: string, sourceId: string]
  /** 触达末页完成阅读事件 */
  completed: []
}>()

const scrollEl = ref<HTMLElement | null>(null)

defineExpose({
  /** 暴露滚动容器 DOM 引用供导航 Hook 执行物理滚动与定位 */
  scrollEl,
})
</script>

<template>
  <main
    ref="scrollEl"
    class="reader-scroll"
    :data-mode="settings.mode"
    :data-pages="settings.pagesPerView"
    tabindex="0"
    @scroll.passive="$emit('scroll', $event)"
    @wheel="$emit('wheel', $event)"
    @touchstart.passive="$emit('userInteract')"
    @pointerdown.passive="$emit('userInteract')"
    @mousemove="$emit('mousemove', $event)"
    @click="$emit('readerClick', $event)"
  >
    <ReaderEndCard
      v-if="rtlHorizontal && showEndCard"
      snap
      class="reader-end-rtl"
      :recommendations="recommendations"
      @back="$emit('backToDetail')"
      @home="$emit('backToShelf')"
      @select="(src, sid) => $emit('selectComic', src, sid)"
      @detail="(src, sid) => $emit('openComicDetail', src, sid)"
      @completed="$emit('completed')"
    />

    <section
      v-for="group in orderedGroups"
      :key="group.index"
      class="reader-spread"
      :data-group-index="group.index"
    >
      <article
        v-for="page in group.pages"
        :key="page"
        class="reader-page"
        :data-page="page"
        :id="`page-${page}`"
      >
        <div class="page-frame" :data-fit="settings.fit">
          <ComicPageImage
            :src="pageFileUrl(source, sourceId, page)"
            :alt="`第 ${toLocalPage(page)} 页`"
            :eager="toLocalPage(page) <= settings.pagesPerView * 3"
            :loading-variant="loadingVariant"
            @ready="$emit('pageReady', page)"
          />
        </div>
        <footer class="page-footer">
          <span>{{ String(toLocalPage(page)).padStart(3, '0') }}</span>
        </footer>
      </article>
    </section>

    <ReaderEndCard
      v-if="!rtlHorizontal && showEndCard"
      :snap="settings.mode === 'horizontal'"
      :recommendations="recommendations"
      @back="$emit('backToDetail')"
      @home="$emit('backToShelf')"
      @select="(src, sid) => $emit('selectComic', src, sid)"
      @detail="(src, sid) => $emit('openComicDetail', src, sid)"
      @completed="$emit('completed')"
    />
  </main>
</template>

<style scoped>
.reader-scroll {
  --pages-per-view: v-bind('settings.pagesPerView');
  position: relative;
  height: 100dvh;
  overflow-y: auto;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 50% 0%, var(--reader-glow), transparent 38rem), var(--reader-bg);
  overscroll-behavior: contain;
  scroll-timeline-name: --reader-scroll;
  scroll-timeline-axis: block;
}

.reader-spread {
  content-visibility: auto;
  contain-intrinsic-block-size: auto 100dvh;
  contain-intrinsic-inline-size: auto 100vw;
}

/* ------------------------------ 页面与图片 ------------------------------ */
.reader-page {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.page-frame {
  width: 100%;
  min-height: 0;
  min-width: 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.page-frame :deep(.comic-page-img) {
  min-height: 40px;
  background: var(--reader-page-bg);
  box-shadow: var(--shadow-3);
}

/* ------------------------------ 竖向连续 ------------------------------ */
.reader-scroll[data-mode='vertical-continuous'] {
  display: block;
  scroll-snap-type: none;
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread {
  min-height: 0;
  display: grid;
  gap: var(--reader-gap-tight);
  grid-template-columns: repeat(var(--pages-per-view), minmax(0, 1fr));
  align-content: start;
  justify-items: center;
  padding: 0 var(--reader-gutter);
  max-width: var(--content-width);
  margin-inline: auto;
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:first-child {
  padding-top: max(
    var(--reader-chrome-h),
    calc(var(--header-h) + env(safe-area-inset-top, 0px) + var(--space-2))
  );
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:not(:first-child) {
  padding-top: var(--reader-gap);
}

.reader-scroll[data-mode='vertical-continuous'] .reader-spread:last-of-type {
  padding-bottom: max(var(--space-6), env(safe-area-inset-bottom, 0px));
}

.reader-scroll[data-mode='vertical-continuous'] .reader-page {
  width: 100%;
  height: auto;
}

.reader-scroll[data-mode='vertical-continuous'] .page-frame {
  height: auto;
}

/* 连续模式 适应宽度：全宽纵向下流 */
.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='width']
  :deep(.comic-page-image) {
  width: 100%;
  height: auto;
}

.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='width']
  :deep(.comic-page-img) {
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: none;
  object-fit: contain;
}

/* 连续模式 适应高度：高度受限，保持整页入目 */
.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='height']
  :deep(.comic-page-image) {
  width: 100%;
  height: auto;
  display: flex;
  justify-content: center;
}

.reader-scroll[data-mode='vertical-continuous']
  .page-frame[data-fit='height']
  :deep(.comic-page-img) {
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
  object-fit: contain;
}

/* ------------------------------ 竖向翻页 ------------------------------ */
.reader-scroll[data-mode='vertical-paged'] {
  display: block;
  scroll-snap-type: y proximity;
}

.reader-scroll[data-mode='vertical-paged'] .reader-spread {
  height: 100dvh;
  min-height: 100dvh;
  display: grid;
  gap: var(--reader-gap);
  grid-template-columns: repeat(var(--pages-per-view), minmax(0, 1fr));
  align-content: center;
  justify-items: center;
  padding: var(--reader-chrome-h) var(--reader-gutter) var(--space-4);
  scroll-snap-align: start;
  scroll-snap-stop: always;
  box-sizing: border-box;
}

.reader-scroll[data-mode='vertical-paged'] .reader-page {
  height: 100%;
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
  width: 100%;
  justify-content: center;
}

.reader-scroll[data-mode='vertical-paged'] .page-frame {
  flex: 1;
  height: 100%;
}

.reader-scroll[data-mode='vertical-paged'] .page-frame :deep(.comic-page-image) {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.reader-scroll[data-mode='vertical-paged'] .page-frame :deep(.comic-page-img) {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

/* ------------------------------ 横向翻页 ------------------------------ */
.reader-scroll[data-mode='horizontal'] {
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  scrollbar-width: none;
  scroll-timeline-axis: inline;
}

.reader-scroll[data-mode='horizontal']::-webkit-scrollbar {
  display: none;
}

.reader-scroll[data-mode='horizontal'] .reader-spread {
  flex: 0 0 100%;
  min-width: 100%;
  height: 100dvh;
  display: grid;
  gap: var(--reader-gap-tight);
  grid-template-columns: repeat(var(--pages-per-view), minmax(0, 1fr));
  align-content: center;
  justify-items: center;
  padding: var(--reader-chrome-h) var(--reader-gutter) var(--space-4);
  scroll-snap-align: start;
  scroll-snap-stop: always;
  box-sizing: border-box;
}

.reader-scroll[data-mode='horizontal'] .reader-page {
  height: 100%;
  max-height: calc(100dvh - var(--reader-chrome-h) - var(--reader-frame-pad-v));
  width: 100%;
  justify-content: center;
}

.reader-scroll[data-mode='horizontal'] .page-frame {
  flex: 1;
  height: 100%;
}

.reader-scroll[data-mode='horizontal'] .page-frame :deep(.comic-page-image) {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.reader-scroll[data-mode='horizontal'] .page-frame :deep(.comic-page-img) {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.page-footer {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted);
  letter-spacing: 0.16em;
}

/* ---------------- 连续模式页面进场（view-timeline 增强） ----------------
   支持 view() 的浏览器在连续模式下提供微位移与淡入（≤6px），提升翻阅物理质感；
   采用 entry 0% entry 100% 覆盖区间，确保超高条漫切页也能稳定过渡；
   并在 prefers-reduced-motion: reduce 下秒级静默禁用。 */
@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    .reader-scroll[data-mode='vertical-continuous'] .reader-page {
      animation: reader-page-appear 1ms var(--ease-out) both;
      animation-timeline: view();
      animation-range: entry 0% entry 100%;
    }

    @keyframes reader-page-appear {
      from {
        opacity: 0.15;
        transform: translateY(6px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
  }
}
</style>

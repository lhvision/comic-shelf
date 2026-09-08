<script setup lang="ts">
import { ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import { coverSrcset } from '@/api/client'

defineProps<{
  covers: string[]
  title: string
}>()

const track = ref<HTMLElement | null>(null)

function scrollToSlide(slide: HTMLElement | null) {
  if (!slide) return
  slide.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
}

function scrollByStep(direction: number) {
  const el = track.value
  if (!el) return
  const slides = Array.from(el.querySelectorAll<HTMLElement>('.cover-slide'))
  if (!slides.length) return

  // 计算视口当前的水平几何中心，找出物理距离中心最近的卡片
  const trackCenter = el.scrollLeft + el.clientWidth / 2
  let closestIndex = 0
  let minDistance = Number.POSITIVE_INFINITY

  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i]
    if (!slide) continue
    const slideCenter = slide.offsetLeft + slide.offsetWidth / 2
    const dist = Math.abs(slideCenter - trackCenter)
    if (dist < minDistance) {
      minDistance = dist
      closestIndex = i
    }
  }

  const targetIndex = Math.max(0, Math.min(slides.length - 1, closestIndex + direction))
  scrollToSlide(slides[targetIndex] ?? null)
}

function onSlideClick(index: number) {
  const el = track.value
  if (!el) return
  const slides = el.querySelectorAll<HTMLElement>('.cover-slide')
  scrollToSlide(slides[index] ?? null)
}
</script>

<template>
  <div class="cover-carousel">
    <div v-if="covers.length > 1" class="carousel-actions">
      <button
        class="carousel-arrow icon-btn"
        type="button"
        aria-label="上一张封面"
        title="上一张封面"
        @click="scrollByStep(-1)"
      >
        <AppIcon name="arrow-left" size="sm" />
      </button>
      <button
        class="carousel-arrow icon-btn"
        type="button"
        aria-label="下一张封面"
        title="下一张封面"
        @click="scrollByStep(1)"
      >
        <AppIcon name="arrow-right" size="sm" />
      </button>
    </div>

    <div
      ref="track"
      class="cover-track"
      tabindex="0"
      role="region"
      :aria-label="`${title} 封面预览`"
    >
      <figure
        v-for="(cover, index) in covers"
        :key="cover"
        class="cover-slide"
        role="button"
        tabindex="0"
        :aria-label="`居中展示第 ${index + 1} 张封面`"
        @click="onSlideClick(index)"
        @keydown.enter.prevent="onSlideClick(index)"
        @keydown.space.prevent="onSlideClick(index)"
      >
        <div
          class="cover-slide-inner"
          :style="index === 0 ? { viewTransitionName: 'comic-cover-active' } : undefined"
        >
          <img
            class="cover-image"
            :src="cover"
            :srcset="coverSrcset(cover)"
            sizes="(max-width: 680px) 75vw, 360px"
            :alt="`${title} 第 ${index + 1} 页封面`"
            :loading="index < 2 ? 'eager' : 'lazy'"
            decoding="async"
          />
          <span class="cover-label">{{ String(index + 1).padStart(2, '0') }}</span>
        </div>
        <figcaption class="cover-caption">
          <span class="cover-no">{{ String(index + 1).padStart(2, '0') }}</span>
          <span>封面 / 首页 {{ index + 1 }}</span>
        </figcaption>
      </figure>
    </div>
  </div>
</template>

<style scoped>
.cover-carousel {
  position: relative;
}

.cover-track {
  display: flex;
  gap: clamp(1rem, 3vw, 2rem);
  overflow-x: auto;
  overflow-y: hidden;
  padding-block: var(--space-5) var(--space-4);
  padding-inline: max(var(--space-4), calc((100% - 16rem) / 2));
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  scrollbar-width: none;
}

.cover-track::-webkit-scrollbar {
  display: none;
}

.cover-slide {
  flex: 0 0 min(15rem, 68vw);
  scroll-snap-align: center;
  scroll-snap-stop: always;
  margin: 0;
  cursor: pointer;
}

.cover-slide-inner {
  position: relative;
  aspect-ratio: 3 / 4.15;
  overflow: hidden;
  border-radius: var(--radius-2);
  border: 1px solid color-mix(in oklab, var(--ink-0) 16%, transparent);
  background: var(--paper-2);
  box-shadow: var(--shadow-2);
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-label {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  padding: var(--space-0-5) var(--space-2);
  background: color-mix(in oklab, var(--ink-0) 78%, transparent);
  color: var(--paper-0);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-size-adjust: ch-width 0.48;
  letter-spacing: 0.08em;
}

.cover-caption {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.cover-no {
  color: var(--accent);
  letter-spacing: 0.1em;
}

.carousel-actions {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 5;
  display: flex;
  justify-content: space-between;
  width: min(58rem, calc(100% - 1rem));
  translate: -50% -50%;
  pointer-events: none;
}

.carousel-arrow {
  pointer-events: auto;
}

/* Scroll-driven cover-flow. Browsers without animation-timeline still get
   a normal scroll-snap carousel above. */
@supports (animation-timeline: view()) {
  .cover-slide {
    view-timeline-name: --cover-slide;
    view-timeline-axis: inline;
    animation: cover-flow linear both;
    animation-timeline: --cover-slide;
    animation-range: cover 0% cover 100%;
    perspective: 42rem;
    transform-style: preserve-3d;
  }

  .cover-slide-inner {
    animation: cover-shade linear both;
    animation-timeline: --cover-slide;
    animation-range: cover 0% cover 100%;
  }
}

@keyframes cover-flow {
  0% {
    transform: translateX(-30%) rotateY(-38deg) translateZ(-5rem) scale(0.72);
    opacity: 0.3;
  }
  45% {
    transform: translateX(0) rotateY(0deg) translateZ(1.2rem) scale(1.05);
    opacity: 1;
  }
  55% {
    transform: translateX(0) rotateY(0deg) translateZ(1.2rem) scale(1.05);
    opacity: 1;
  }
  100% {
    transform: translateX(30%) rotateY(38deg) translateZ(-5rem) scale(0.72);
    opacity: 0.3;
  }
}

@keyframes cover-shade {
  0% {
    filter: brightness(0.55);
  }
  45%,
  55% {
    filter: none;
  }
  100% {
    filter: brightness(0.55);
  }
}

/* 原生 CSS Carousel (Chrome 135+ / CSS Overflow 5) 渐进增强：
   在支持的现代浏览器中，由内核直接生成无 JS 纸印指示标记 */
@supports (scroll-marker-group: after) {
  .cover-track {
    scroll-marker-group: after;
  }

  .cover-slide::scroll-marker {
    content: '';
    display: inline-block;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: var(--radius-full);
    background: var(--line-strong);
    cursor: pointer;
    transition: all var(--duration-2) var(--ease-out);
  }

  .cover-slide::scroll-marker:target-current {
    background: var(--accent);
    transform: scale(1.25);
  }

  .cover-slide::scroll-marker:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  ::scroll-marker-group {
    display: flex;
    justify-content: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }
}

@media (max-width: 640px) {
  /* 移动端封面顶部给返回按钮留一条窄空间，左右切换保持 PC 同款居中位置 */
  .cover-track {
    padding-top: calc(var(--control-xs) + var(--space-3));
  }
}
</style>

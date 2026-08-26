<script setup lang="ts">
import { ref } from 'vue'
defineProps<{
  covers: string[]
  title: string
}>()

const track = ref<HTMLElement | null>(null)

function scrollByCard(direction: number) {
  const el = track.value
  if (!el) return
  const first = el.querySelector<HTMLElement>('.cover-slide')
  const width = first ? first.getBoundingClientRect().width : el.clientWidth * 0.5
  const gap = first
    ? Number.parseFloat(getComputedStyle(first.parentElement ?? el).columnGap || '0')
    : 0
  el.scrollBy({ left: direction * (width + gap), behavior: 'smooth' })
}
</script>

<template>
  <div class="cover-carousel">
    <div class="carousel-actions">
      <button
        class="carousel-arrow icon-btn"
        type="button"
        aria-label="上一张封面"
        title="上一张封面"
        @click="scrollByCard(-1)"
      >
        ←
      </button>
      <button
        class="carousel-arrow icon-btn"
        type="button"
        aria-label="下一张封面"
        title="下一张封面"
        @click="scrollByCard(1)"
      >
        →
      </button>
    </div>

    <div
      ref="track"
      class="cover-track"
      tabindex="0"
      role="region"
      :aria-label="`${title} 封面预览`"
    >
      <figure v-for="(cover, index) in covers" :key="cover" class="cover-slide">
        <div
          class="cover-slide-inner"
          :style="index === 0 ? { viewTransitionName: 'comic-cover-active' } : undefined"
        >
          <img
            class="cover-image"
            :src="cover"
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
}

.cover-slide-inner {
  aspect-ratio: 3 / 4.15;
  overflow: hidden;
  border-radius: var(--radius-2);
  border: 1px solid color-mix(in oklab, var(--ink-0) 16%, transparent);
  background: var(--paper-2);
  box-shadow: var(--shadow-2);
}

.cover-slide-inner {
  position: relative;
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

@media (max-width: 640px) {
  /* 移动端封面顶部给返回按钮留一条窄空间，左右切换保持 PC 同款居中位置 */
  .cover-track {
    padding-top: calc(var(--control-xs) + var(--space-3));
  }
}
</style>

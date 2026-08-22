<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 1 | 2 | 3 | 4
    text?: string
    compact?: boolean
  }>(),
  {
    variant: 1,
    text: '正在装订书页…',
    compact: false,
  },
)

const illustrationSrc = computed(() => `/loading-${props.variant}.webp`)
</script>

<template>
  <div
    class="reader-loading-state"
    :class="{ 'is-compact': compact }"
    role="status"
    aria-live="polite"
  >
    <div class="loading-card">
      <div class="illustration-frame">
        <img
          class="illustration-img"
          :src="illustrationSrc"
          alt="加载中插画"
          aria-hidden="true"
          loading="eager"
          decoding="async"
        />
        <div class="shimmer-overlay" aria-hidden="true" />
      </div>

      <div class="loading-meta">
        <span class="pulse-indicator" aria-hidden="true" />
        <span class="loading-text">{{ text }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reader-loading-state {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  pointer-events: none;
  user-select: none;
}

.loading-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2-5);
  padding: var(--space-3) var(--space-3) var(--space-2-5);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0, #f8f6f0) 8%, transparent);
  border: 1px solid color-mix(in oklab, var(--line, #e2ded5) 16%, transparent);
  box-shadow: 0 12px 32px -6px rgb(0 0 0 / 48%);
  backdrop-filter: blur(14px);
  max-width: min(84vw, 18.5rem);
  width: 100%;
  animation: loading-breathe 2.8s var(--ease-out) infinite;
}

.reader-loading-state.is-compact .loading-card {
  max-width: min(76vw, 14.5rem);
  padding: var(--space-2) var(--space-2) var(--space-1-5);
  gap: var(--space-1-5);
}

.illustration-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--ink-0, #141311) 22%, transparent);
  border: 1px solid color-mix(in oklab, var(--paper-0, #f8f6f0) 10%, transparent);
}

.illustration-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  /* 降低饱和度与对比度，温和不抢戏 */
  filter: saturate(0.68) contrast(0.92) brightness(0.88);
  transition: filter var(--duration-2) var(--ease-out);
}

.shimmer-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    110deg,
    transparent 15%,
    color-mix(in oklab, var(--paper-0, #ffffff) 36%, transparent) 50%,
    transparent 85%
  );
  translate: -100% 0;
  animation: shimmer-sweep 2.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.loading-meta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted, #938d80);
  letter-spacing: 0.08em;
}

.pulse-indicator {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 999px;
  background: var(--accent);
  box-shadow: 0 0 0 0 color-mix(in oklab, var(--accent) 40%, transparent);
  animation: pulse-dot 1.8s var(--ease-out) infinite;
}

.loading-text {
  font-size: var(--text-xs);
  line-height: 1.4;
}

@keyframes shimmer-sweep {
  to {
    translate: 100% 0;
  }
}

@keyframes pulse-dot {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in oklab, var(--accent) 35%, transparent);
  }
  50% {
    box-shadow: 0 0 0 5px color-mix(in oklab, var(--accent) 0%, transparent);
  }
}

@keyframes loading-breathe {
  0%,
  100% {
    transform: scale(0.985);
    opacity: 0.88;
  }
  50% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .loading-card,
  .shimmer-overlay,
  .pulse-indicator {
    animation: none;
  }
}
</style>

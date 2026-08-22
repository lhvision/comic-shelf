<script setup lang="ts">
import { computed } from 'vue'
import { useIllustrationPool } from '@/composables/useIllustrationPool'

const props = withDefaults(
  defineProps<{
    variant?: number | string
    text?: string
    compact?: boolean
    fullFrame?: boolean
  }>(),
  {
    variant: undefined,
    text: '正在装订书页…',
    compact: false,
    fullFrame: false,
  },
)

const { getIllustration } = useIllustrationPool()
const illustrationSrc = computed(() => getIllustration(props.variant))
</script>

<template>
  <div
    class="reader-loading-state"
    :class="{ 'is-compact': compact, 'is-full-frame': fullFrame }"
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
  gap: var(--space-3);
  padding: var(--space-3-5, var(--space-4)) var(--space-3-5, var(--space-4)) var(--space-3);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0, #f8f6f0) 8%, transparent);
  border: 1px solid color-mix(in oklab, var(--line, #e2ded5) 16%, transparent);
  box-shadow: 0 16px 36px -6px rgb(0 0 0 / 52%);
  backdrop-filter: blur(14px);
  max-width: min(88vw, 24rem);
  width: 100%;
  animation: loading-breathe 2.8s var(--ease-out) infinite;
}

/* 全幅漫画大尺寸模式：与漫画视口等比呼应，展现大尺寸看板插画 */
.reader-loading-state.is-full-frame .loading-card {
  max-width: min(92%, 34rem);
  padding: var(--space-4) var(--space-4) var(--space-3-5, var(--space-4));
  gap: var(--space-3-5, var(--space-4));
  border-radius: var(--radius-3);
}

.reader-loading-state.is-full-frame .illustration-frame {
  aspect-ratio: 16 / 10;
  max-height: clamp(14rem, 42vh, 28rem);
}

/* 紧凑微型模式 */
.reader-loading-state.is-compact:not(.is-full-frame) .loading-card {
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
  filter: saturate(0.72) contrast(0.92) brightness(0.9);
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
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--reader-muted, #938d80);
  letter-spacing: 0.08em;
}

.pulse-indicator {
  width: 0.45rem;
  height: 0.45rem;
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
    transform: scale(0.988);
    opacity: 0.9;
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

@media (max-width: 640px) {
  .reader-loading-state.is-full-frame .loading-card {
    max-width: 90vw;
    padding: var(--space-3);
  }
}
</style>

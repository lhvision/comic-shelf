<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useSlots, watch } from 'vue'
import { useHtmlCanvas } from '@/composables/useHtmlCanvas'
import { withResolvers } from '@/utils/promise'

/**
 * Experimental HTML-in-Canvas surface.
 *
 * The default slot is a complete DOM subtree (many nodes: image + headings +
 * chips + progress bar...). When the browser supports the Origin Trial API and
 * the experiment is enabled, that DOM subtree is drawn into one canvas.
 * A transparent overlay slot keeps interactions alive; text selection and
 * accessibility intentionally stay in the DOM fallback path.
 */
const props = withDefaults(
  defineProps<{
    enabled?: boolean
    surface?: string
    /** Change to force a re-draw of the captured DOM (e.g. live progress). */
    redrawKey?: string | number
  }>(),
  { enabled: false, surface: 'dom-surface', redrawKey: '' },
)

const slots = useSlots()
const { supported, getContext, publishStatus } = useHtmlCanvas()

const domLayer = ref<HTMLElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const attemptCanvas = ref(false)
const canvasReady = ref(false)
const drawFailed = ref(false)
let drawTimer = 0

const hasOverlay = computed(() => Boolean(slots.overlay))
const renderer = computed<'canvas' | 'dom'>(() => {
  if (attemptCanvas.value && canvasReady.value) return 'canvas'
  return 'dom'
})

function shouldAttempt() {
  return props.enabled && supported.value
}

async function draw() {
  if (!shouldAttempt()) {
    attemptCanvas.value = false
    canvasReady.value = false
    return
  }

  attemptCanvas.value = true
  await nextTick()

  const layer = domLayer.value
  const canvas = canvasEl.value
  if (!layer || !canvas) return

  // Wait for every image inside the DOM subtree; otherwise the canvas would
  // capture empty/broken image boxes.
  // 结合 img.decode() 异步离屏解码管线与 Promise.withResolvers() 状态解耦
  const images = [...layer.querySelectorAll('img')]
  await Promise.all(
    images.map(async (img) => {
      if (!img.complete) {
        const { promise, resolve } = withResolvers<void>()
        img.addEventListener('load', () => resolve(), { once: true })
        img.addEventListener('error', () => resolve(), { once: true })
        await promise
      }
      try {
        if (typeof img.decode === 'function') {
          await img.decode()
        }
      } catch {
        // 损坏或空图容错，不中断整体绘制
      }
    }),
  )

  const rect = layer.getBoundingClientRect()
  if (rect.width < 2 || rect.height < 2) return

  canvas.width = Math.max(1, Math.round(rect.width))
  canvas.height = Math.max(1, Math.round(rect.height))

  try {
    const ctx = getContext(canvas)
    if (!ctx || typeof ctx.drawElement !== 'function') {
      throw new Error('HTML canvas context unavailable')
    }
    ctx.drawElement(layer, 0, 0)
    canvasReady.value = true
    drawFailed.value = false
    publishStatus(true, props.surface)
  } catch {
    canvasReady.value = false
    drawFailed.value = true
    publishStatus(false, props.surface)
  }
}

function scheduleDraw() {
  window.clearTimeout(drawTimer)
  drawTimer = window.setTimeout(draw, 80)
}

onMounted(() => {
  if (!shouldAttempt()) {
    publishStatus(false, props.surface)
    return
  }
  scheduleDraw()
})

onBeforeUnmount(() => {
  window.clearTimeout(drawTimer)
})

watch(
  () => [props.enabled, supported.value] as const,
  () => {
    if (!shouldAttempt()) {
      attemptCanvas.value = false
      canvasReady.value = false
      drawFailed.value = false
      publishStatus(false, props.surface)
      return
    }
    scheduleDraw()
  },
)

// Live data (e.g. cache progress) inside the slot should re-paint the canvas.
watch(
  () => props.redrawKey,
  () => {
    if (canvasReady.value) scheduleDraw()
  },
)
</script>

<template>
  <div
    class="html-canvas-surface"
    :data-renderer="renderer"
    :data-canvas-active="canvasReady || undefined"
  >
    <div ref="domLayer" class="surface-dom" :inert="canvasReady || undefined">
      <slot />
    </div>

    <canvas v-if="attemptCanvas" ref="canvasEl" class="surface-canvas" aria-hidden="true" />

    <div v-if="attemptCanvas && !canvasReady && !drawFailed" class="surface-loading" role="status">
      <img src="/loading-1.webp" alt="" aria-hidden="true" />
    </div>

    <div v-if="hasOverlay" class="surface-overlay">
      <slot name="overlay" />
    </div>

    <span v-if="attemptCanvas" class="surface-badge" :data-active="canvasReady">
      {{ canvasReady ? 'CANVAS' : drawFailed ? 'DOM' : 'CANVAS…' }}
    </span>
  </div>
</template>

<style scoped>
.html-canvas-surface {
  position: relative;
  isolation: isolate;
}

.surface-dom {
  position: relative;
  z-index: 0;
  transition: opacity var(--duration-2) var(--ease-out);
}

.html-canvas-surface[data-canvas-active] .surface-dom {
  opacity: 0;
}

.surface-canvas {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: fill;
}

.surface-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  border-radius: inherit;
}

.surface-loading {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: grid;
  place-items: center;
  pointer-events: none;
}

.surface-loading img {
  width: clamp(2.5rem, 42%, 4.5rem);
  height: auto;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: var(--radius-1);
  filter: saturate(0.68) contrast(0.92) brightness(0.88);
  border: 1px solid color-mix(in oklab, var(--paper-0, #fff) 12%, transparent);
}

.surface-badge {
  position: absolute;
  left: 0.55rem;
  bottom: 0.55rem;
  z-index: 5;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  background: rgb(10 10 10 / 58%);
  color: rgb(255 255 255 / 68%);
  font-family: var(--font-mono);
  font-size: 0.58rem;
  letter-spacing: 0.08em;
  pointer-events: none;
}

.surface-badge[data-active='true'] {
  background: color-mix(in oklab, var(--accent) 78%, rgb(0 0 0 / 55%));
  color: #fff;
}
</style>

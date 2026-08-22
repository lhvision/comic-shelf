<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import { useViewTransition } from '@/composables/useViewTransition'

const props = defineProps<{
  source: string
  sourceId: string
  favorite: boolean
}>()

const emit = defineEmits<{
  toggled: [favorite: boolean]
}>()

const btnRef = ref<HTMLButtonElement | null>(null)
const busy = ref(false)
const { withViewTransition } = useViewTransition()

async function toggle() {
  if (busy.value) return
  busy.value = true
  const next = !props.favorite
  try {
    await api.setFavorite(props.source, props.sourceId, next)
    await withViewTransition(
      () => {
        emit('toggled', next)
      },
      { element: btnRef.value },
    )
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <button
    ref="btnRef"
    class="favorite-button"
    type="button"
    :aria-pressed="favorite"
    :aria-label="favorite ? '取消喜欢' : '标记喜欢'"
    :disabled="busy"
    @click.stop.prevent="toggle"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 20.7 4.9 13.5a4.75 4.75 0 0 1 0-6.6 4.6 4.6 0 0 1 6.5 0l.6.6.6-.6a4.6 4.6 0 0 1 6.5 0 4.75 4.75 0 0 1 0 6.6L12 20.7Z"
      />
    </svg>
    <span class="visually-hidden">{{ favorite ? '已喜欢' : '喜欢' }}</span>
  </button>
</template>

<style scoped>
.favorite-button {
  position: absolute;
  top: 0.55rem;
  left: 0.55rem;
  z-index: 6;
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid rgb(255 255 255 / 22%);
  border-radius: 50%;
  background: rgb(8 8 8 / 46%);
  color: #fff;
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 8px rgb(0 0 0 / 35%);
  transition:
    transform var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.favorite-button:hover {
  transform: scale(1.08);
}

.favorite-button svg {
  width: 1.1rem;
  height: 1.1rem;
  fill: transparent;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linejoin: round;
  stroke-linecap: round;
  transition: fill var(--duration-1) var(--ease-out);
}

.favorite-button[aria-pressed='true'] {
  background: color-mix(in oklab, var(--accent) 82%, rgb(0 0 0 / 45%));
  color: #fff;
  border-color: transparent;
}

.favorite-button[aria-pressed='true'] svg {
  fill: currentColor;
}

.favorite-button:disabled {
  cursor: wait;
  opacity: 0.7;
}
</style>

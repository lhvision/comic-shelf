<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import { useViewTransition } from '@/composables/useViewTransition'
import AppIcon from '@/components/AppIcon.vue'

const props = withDefaults(
  defineProps<{
    source: string
    sourceId: string
    favorite: boolean
    interactive?: boolean
  }>(),
  { interactive: true },
)

const emit = defineEmits<{
  toggled: [favorite: boolean]
}>()

const btnRef = ref<HTMLButtonElement | null>(null)
const busy = ref(false)
const { withViewTransition } = useViewTransition()

async function toggle() {
  if (!props.interactive || busy.value) return
  busy.value = true
  const next = !props.favorite
  try {
    await withViewTransition(
      async () => {
        emit('toggled', next)
        await api.setFavorite(props.source, props.sourceId, next)
      },
      { scope: btnRef.value },
    )
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <button
    v-if="interactive"
    ref="btnRef"
    class="favorite-button"
    type="button"
    :aria-pressed="favorite"
    :aria-label="favorite ? '取消喜欢' : '标记喜欢'"
    :disabled="busy"
    @click.stop.prevent="toggle"
  >
    <AppIcon :name="favorite ? 'heart-filled' : 'heart'" size="md" />
    <span class="visually-hidden">{{ favorite ? '已喜欢' : '喜欢' }}</span>
  </button>
  <div v-else-if="favorite" class="favorite-badge" aria-label="已标记喜欢" role="img">
    <AppIcon name="heart-filled" size="sm" />
    <span class="visually-hidden">已喜欢</span>
  </div>
</template>

<style scoped>
.favorite-button,
.favorite-badge {
  position: absolute;
  top: 0.55rem;
  left: 0.55rem;
  z-index: 6;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  backdrop-filter: blur(8px);
}

.favorite-button {
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid rgb(255 255 255 / 22%);
  background: rgb(8 8 8 / 46%);
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

.favorite-badge {
  width: 1.85rem;
  height: 1.85rem;
  border: 1px solid rgb(255 255 255 / 20%);
  background: color-mix(in oklab, var(--accent) 85%, rgb(0 0 0 / 40%));
  box-shadow: 0 2px 6px rgb(0 0 0 / 30%);
  pointer-events: none;
}

.favorite-badge svg {
  width: 0.95rem;
  height: 0.95rem;
  fill: currentColor;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linejoin: round;
  stroke-linecap: round;
}
</style>

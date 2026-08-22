<script setup lang="ts">
import { ref } from 'vue'
import Modal from '@/components/Modal.vue'

const props = defineProps<{
  previewUrl: string
  isSearching: boolean
}>()

const emit = defineEmits<{
  clear: []
}>()

const isModalOpen = ref(false)
</script>

<template>
  <div class="search-chip">
    <button class="chip-preview-btn" @click="isModalOpen = true" aria-label="查看搜索原图">
      <img :src="previewUrl" alt="搜索原图预览" class="chip-img" />
      <div v-if="isSearching" class="chip-overlay">
        <span class="chip-spinner"></span>
      </div>
    </button>
    <button class="chip-clear-btn" @click="emit('clear')" aria-label="清除图片">
      <svg
        viewBox="0 0 16 16"
        width="12"
        height="12"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        fill="none"
      >
        <path d="M4 4l8 8m0-8l-8 8" />
      </svg>
    </button>

    <Modal :open="isModalOpen" title="搜索图片" @cancel="isModalOpen = false">
      <div class="modal-img-container">
        <img :src="previewUrl" alt="搜索原图" class="modal-img" />
      </div>
    </Modal>
  </div>
</template>

<style scoped>
.search-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  padding: var(--space-1);
  height: 2.4rem;
}

.chip-preview-btn {
  position: relative;
  height: 100%;
  aspect-ratio: 1;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: var(--radius-1);
  overflow: hidden;
  cursor: pointer;
}

.chip-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.chip-overlay {
  position: absolute;
  inset: 0;
  background: color-mix(in oklab, var(--paper-0) 60%, transparent);
  display: grid;
  place-items: center;
}

.chip-spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin var(--duration-3) linear infinite;
}

.chip-clear-btn {
  display: grid;
  place-items: center;
  width: 1.5rem;
  height: 1.5rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ink-2);
  border-radius: var(--radius-1);
  cursor: pointer;
  transition:
    background var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.chip-clear-btn:hover {
  background: var(--paper-2);
  color: var(--ink-0);
}

.modal-img-container {
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--paper-1);
  border-radius: var(--radius-2);
  padding: var(--space-2);
}

.modal-img {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
  border-radius: var(--radius-1);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

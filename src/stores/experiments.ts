import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useHtmlCanvas } from '@/composables/useHtmlCanvas'

const STORAGE_KEY = 'comic-shelf:experiments:v1'

interface ExperimentSettings {
  htmlCanvasCards: boolean
}

function load(): ExperimentSettings {
  try {
    const value = JSON.parse(
      localStorage.getItem(STORAGE_KEY) || '{}',
    ) as Partial<ExperimentSettings>
    return { htmlCanvasCards: value.htmlCanvasCards === true }
  } catch {
    return { htmlCanvasCards: false }
  }
}

export const useExperimentsStore = defineStore('experiments', () => {
  const { supported } = useHtmlCanvas()
  const saved = load()
  const htmlCanvasCards = ref(saved.htmlCanvasCards && supported.value)

  watch(htmlCanvasCards, (value) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ htmlCanvasCards: value }))
  })

  return {
    htmlCanvasCards,
    htmlCanvasSupported: supported,
  }
})

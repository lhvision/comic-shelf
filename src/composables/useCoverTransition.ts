import { ref } from 'vue'

const activeCoverKey = ref<string | null>(null)

export function useCoverTransition() {
  function setActiveCover(source: string, sourceId: string) {
    activeCoverKey.value = `${source}/${sourceId}`
  }

  function clearActiveCover() {
    activeCoverKey.value = null
  }

  function isCoverActive(source: string, sourceId: string) {
    return activeCoverKey.value === `${source}/${sourceId}`
  }

  return {
    setActiveCover,
    clearActiveCover,
    isCoverActive,
  }
}

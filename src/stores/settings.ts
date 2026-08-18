import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'

const STORAGE_KEY = 'comic-shelf:download-concurrency:v1'
const MIN = 1
const MAX = 16

/** 下载并发设置：localStorage 记忆，后端 env(COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS) 锁定优先。 */
export const useAppSettings = defineStore('appSettings', () => {
  const concurrency = ref(3)
  const envControlled = ref(false)
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      const info = await api.downloadConcurrency()
      concurrency.value = info.limit
      envControlled.value = info.env_controlled

      // 后端重启过但前端 localStorage 还记得选择 → 把选择推回后端（env 未锁定时）。
      const saved = Number(localStorage.getItem(STORAGE_KEY))
      if (
        !envControlled.value &&
        Number.isFinite(saved) &&
        saved >= MIN &&
        saved <= MAX &&
        saved !== info.limit
      ) {
        await set(saved)
      }
    } catch {
      /* 后端不支持时保留默认值 */
    } finally {
      loading.value = false
    }
  }

  async function set(value: number) {
    if (envControlled.value) return false
    const next = Math.min(MAX, Math.max(MIN, Math.round(value)))
    concurrency.value = next
    localStorage.setItem(STORAGE_KEY, String(next))
    try {
      const info = await api.setDownloadConcurrency(next)
      concurrency.value = info.limit
      envControlled.value = info.env_controlled
      return true
    } catch {
      return false
    }
  }

  async function inc() {
    if (!envControlled.value) await set(concurrency.value + 1)
  }

  async function dec() {
    if (!envControlled.value) await set(concurrency.value - 1)
  }

  return {
    concurrency,
    envControlled,
    loading,
    min: MIN,
    max: MAX,
    load,
    set,
    inc,
    dec,
  }
})

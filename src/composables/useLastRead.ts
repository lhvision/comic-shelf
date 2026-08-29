import { computed, watch } from 'vue'
import { useDebounceFn, useLocalStorage } from '@vueuse/core'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'
import { api } from '@/api/client'
import { useAuth } from '@/composables/useAuth'

/**
 * 「上次读到哪里」的持久化与多端同步。
 *
 * 结合本地 LocalStorage 瞬时读写响应与后端 SQLite 用户隔离存储；
 * 采用 userId 命名空间隔离本地存储键，并在切换用户/漫画时向服务端拉取强对齐，
 * 翻页更新时以 800ms 防抖静默上报服务端，杜绝跨用户进度泄漏与污染。
 */

export function useLastRead(source: MaybeRefOrGetter<string>, sourceId: MaybeRefOrGetter<string>) {
  const { userId } = useAuth()
  const s = computed(() => toValue(source))
  const sid = computed(() => toValue(sourceId))
  const uid = computed(() => userId.value || 'default')
  const key = computed(() => `comic-shelf:last-read:${uid.value}:${s.value}/${sid.value}`)
  const storage = useLocalStorage<number>(key, 0)

  // 1. 初始化或切换用户/作品时向后端拉取最新进度并强对齐
  watch(
    [s, sid, uid],
    async ([curS, curSid]) => {
      if (!curS || !curSid) return
      try {
        const prog = await api.getReadingProgress(curS, curSid)
        if (prog) {
          storage.value = prog.last_page
        }
      } catch {
        /* offline or network error */
      }
    },
    { immediate: true },
  )

  // 2. 翻页时 800ms 防抖上报到后端用户进度表
  const reportProgress = useDebounceFn((page: number) => {
    if (page > 0 && s.value && sid.value) {
      api.saveReadingProgress(s.value, sid.value, page).catch(() => {})
    }
  }, 800)

  watch(storage, (newPage) => {
    if (newPage > 0) {
      void reportProgress(newPage)
    }
  })

  return storage
}

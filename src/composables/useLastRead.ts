import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'

/**
 * 「上次读到哪里」的本地持久化。
 *
 * key 由 source/sourceId 动态生成（`comic-shelf:last-read:<source>/<sourceId>`），
 * 详情页显示"继续阅读"需要读、阅读器翻页需要写。用 `useLocalStorage` 做响应式绑定，
 * 读侧与写侧拿到同一个对象，无需再手写 getItem/setItem。
 */

export function useLastRead(source: MaybeRefOrGetter<string>, sourceId: MaybeRefOrGetter<string>) {
  const key = computed(() => `comic-shelf:last-read:${toValue(source)}/${toValue(sourceId)}`)
  return useLocalStorage<number>(key, 0)
}

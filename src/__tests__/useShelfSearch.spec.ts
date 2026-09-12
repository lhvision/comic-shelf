import { describe, it, expect, vi } from 'vite-plus/test'
import { computed, effectScope, nextTick, ref } from 'vue'
import type { Router } from 'vue-router'
import { useShelfSearch } from '@/composables/useShelfSearch'
import type { LibrarySummary } from '@/types'

describe('useShelfSearch', () => {
  it('initializes and orchestrates shelfSearch and dialogueQuery isolation', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const activeSource = computed(() => 'local')
      const shelfSearch = ref('')
      const filteredItems = computed<LibrarySummary[]>(() => [])
      const allItems = computed<LibrarySummary[]>(() => [])
      const router = { push: vi.fn<() => Promise<void>>() } as unknown as Router
      const toast = vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => number>()

      const {
        searchInput,
        searchActiveCommand,
        dialogueQuery,
        handleSelectCommand,
        handleClearCommand,
      } = useShelfSearch({
        activeSource,
        shelfSearch,
        filteredItems,
        allItems,
        router,
        toast,
      })

      expect(searchInput.value).toBe('')
      expect(searchActiveCommand.value).toBeNull()

      // 1. Regular search typing updates shelfSearch
      searchInput.value = 'JOJO'
      await nextTick()
      expect(shelfSearch.value).toBe('JOJO')
      expect(dialogueQuery.value).toBe('')

      // 2. Select dialogue command
      handleSelectCommand({
        id: 'dialogue',
        name: '/台词',
        label: '台词',
        icon: 'message-square',
        aliases: ['d'],
        description: '检索分镜台词',
        placeholder: '输入台词',
      })
      await nextTick()

      expect(searchActiveCommand.value).toBe('dialogue')
      expect(searchInput.value).toBe('')
      // Shelf search must be frozen to empty string
      expect(shelfSearch.value).toBe('')

      // 3. Dialogue query typing in dialogue mode updates dialogueQuery only
      searchInput.value = '波纹'
      await nextTick()
      expect(dialogueQuery.value).toBe('波纹')
      expect(shelfSearch.value).toBe('')

      // 4. Clearing command restores regular mode
      handleClearCommand()
      await nextTick()
      expect(searchActiveCommand.value).toBeNull()
      expect(dialogueQuery.value).toBe('')
    })
    scope.stop()
  })
})

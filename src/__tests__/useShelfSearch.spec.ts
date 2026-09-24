import { describe, it, expect, vi } from 'vite-plus/test'
import { computed, effectScope, nextTick, ref } from 'vue'
import type { Router } from 'vue-router'
import { useShelfSearch } from '@/composables/useShelfSearch'
import type { DialogueSearchItem, LibrarySummary } from '@/types'

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

  it('reports the dialogue listbox as shown only when results are actually rendered', () => {
    const scope = effectScope()
    scope.run(() => {
      const {
        isDialogueOpen,
        isDialogueSearching,
        dialogueError,
        dialogueResults,
        isDialogueListboxShown,
      } = useShelfSearch({
        activeSource: computed(() => 'local'),
        shelfSearch: ref(''),
        filteredItems: computed<LibrarySummary[]>(() => []),
        allItems: computed<LibrarySummary[]>(() => []),
        router: { push: vi.fn<() => Promise<void>>() } as unknown as Router,
        toast: vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => number>(),
      })

      // 输入框的 aria-expanded 据此设置：浮层开着但 listbox 不存在时必须为假，否则指向空节点
      isDialogueOpen.value = true
      expect(isDialogueListboxShown.value).toBe(false)

      dialogueResults.value = [
        { source: 'local', source_id: 'a', page_index: 1 } as DialogueSearchItem,
      ]
      expect(isDialogueListboxShown.value).toBe(true)

      isDialogueSearching.value = true
      expect(isDialogueListboxShown.value).toBe(false)
      isDialogueSearching.value = false

      dialogueError.value = '检索失败'
      expect(isDialogueListboxShown.value).toBe(false)
      dialogueError.value = ''

      isDialogueOpen.value = false
      expect(isDialogueListboxShown.value).toBe(false)
    })
    scope.stop()
  })
})

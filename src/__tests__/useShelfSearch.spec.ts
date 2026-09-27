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
      // 检索刷新期间列表继续保留在 DOM 中，避免视觉闪烁并维持 listbox 无障碍关联
      expect(isDialogueListboxShown.value).toBe(true)
      isDialogueSearching.value = false

      dialogueResults.value = []
      expect(isDialogueListboxShown.value).toBe(false)
      dialogueResults.value = [
        { source: 'local', source_id: 'a', page_index: 1 } as DialogueSearchItem,
      ]

      dialogueError.value = '检索失败'
      expect(isDialogueListboxShown.value).toBe(false)
      dialogueError.value = ''

      isDialogueOpen.value = false
      expect(isDialogueListboxShown.value).toBe(false)
    })
    scope.stop()
  })

  it('preserves existing shelfSearch and shelfCommand across mounts (session retention)', () => {
    const scope = effectScope()
    scope.run(() => {
      const shelfSearch = ref('魔女')
      const shelfCommand = ref<'author' | null>('author')

      const { searchInput, searchActiveCommand } = useShelfSearch({
        activeSource: computed(() => 'local'),
        shelfSearch,
        shelfCommand,
        filteredItems: computed<LibrarySummary[]>(() => []),
        allItems: computed<LibrarySummary[]>(() => []),
        router: { push: vi.fn<() => Promise<void>>() } as unknown as Router,
        toast: vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => number>(),
      })

      // 验证未被空初态擦除
      expect(searchInput.value).toBe('魔女')
      expect(searchActiveCommand.value).toBe('author')
      expect(shelfSearch.value).toBe('魔女')
    })
    scope.stop()
  })

  it('manages search history visibility and selection', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const shelfSearch = ref('')
      const router = { push: vi.fn<() => Promise<void>>() } as unknown as Router
      const toast = vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => number>()

      const {
        searchInput,
        isHistoryOpen,
        isHistoryListboxShown,
        searchHistory,
        onSearchFocus,
        handleSelectHistory,
        handleClearHistory,
        commitSearchHistory,
      } = useShelfSearch({
        activeSource: computed(() => 'local'),
        shelfSearch,
        filteredItems: computed<LibrarySummary[]>(() => []),
        allItems: computed<LibrarySummary[]>(() => []),
        router,
        toast,
      })

      handleClearHistory()
      expect(searchHistory.value.length).toBe(0)

      // 1. 无历史时聚焦不展开
      onSearchFocus()
      expect(isHistoryOpen.value).toBe(false)

      // 2. 模拟用户输入并回车提交搜索
      searchInput.value = '东方'
      commitSearchHistory()
      expect(searchHistory.value.length).toBe(1)
      expect(searchHistory.value[0]?.query).toBe('东方')

      // 3. 清空输入框后重新聚焦，展开历史选单
      searchInput.value = ''
      await nextTick()
      onSearchFocus()
      expect(isHistoryOpen.value).toBe(true)
      expect(isHistoryListboxShown.value).toBe(true)

      // 4. 输入字符时历史选单自动隐藏
      searchInput.value = '新词'
      await nextTick()
      expect(isHistoryOpen.value).toBe(false)
      expect(isHistoryListboxShown.value).toBe(false)

      // 5. 点击历史项快速填词
      searchInput.value = ''
      await nextTick()
      handleSelectHistory(searchHistory.value[0]!)
      await nextTick()
      expect(searchInput.value).toBe('东方')
      expect(shelfSearch.value).toBe('东方')
    })
    scope.stop()
  })

  it('computes clean combobox ARIA attributes reactively without template nested ternaries', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const shelfSearch = ref('')
      const router = { push: vi.fn<() => Promise<void>>() } as unknown as Router
      const toast = vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => number>()

      const {
        searchInput,
        isComboboxExpanded,
        activeComboboxControls,
        activeComboboxActivedescendant,
        isCommandMenuOpen,
        commandMenuFocusedIndex,
        isHistoryOpen,
        historyFocusedIndex,
        searchHistory,
        onSearchKeydown,
        commitSearchHistory,
        handleClearHistory,
      } = useShelfSearch({
        activeSource: computed(() => 'local'),
        shelfSearch,
        filteredItems: computed<LibrarySummary[]>(() => []),
        allItems: computed<LibrarySummary[]>(() => []),
        router,
        toast,
      })

      handleClearHistory()

      // 初态：无浮层展开
      expect(isComboboxExpanded.value).toBe(false)
      expect(activeComboboxControls.value).toBeUndefined()
      expect(activeComboboxActivedescendant.value).toBeUndefined()

      // 1. 输入 / 唤醒快捷指令选单
      searchInput.value = '/'
      await nextTick()
      expect(isCommandMenuOpen.value).toBe(true)
      expect(isComboboxExpanded.value).toBe(true)
      expect(activeComboboxControls.value).toBe('search-command-menu')
      expect(activeComboboxActivedescendant.value).toBe(`cmd-opt-${commandMenuFocusedIndex.value}`)

      // 2. 存在历史记录时，空输入框按下向下键唤醒历史浮层
      searchInput.value = '测试词条'
      commitSearchHistory()
      expect(searchHistory.value.length).toBe(1)

      searchInput.value = ''
      await nextTick()
      expect(isHistoryOpen.value).toBe(false)

      // 按下 ArrowDown 主动唤醒历史浮层
      onSearchKeydown(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
      expect(isHistoryOpen.value).toBe(true)
      expect(isComboboxExpanded.value).toBe(true)
      expect(activeComboboxControls.value).toBe('search-history-menu')
      expect(activeComboboxActivedescendant.value).toBe(`history-opt-${historyFocusedIndex.value}`)

      // 3. 键盘按下 Delete 键删除当前高亮的历史项
      onSearchKeydown(new KeyboardEvent('keydown', { key: 'Delete' }))
      expect(searchHistory.value.length).toBe(0)
      expect(isHistoryOpen.value).toBe(false)
      expect(isComboboxExpanded.value).toBe(false)

      // 4. 输入未决指令（如 /abc）时 commitSearchHistory 不入库
      searchInput.value = '/abc'
      commitSearchHistory()
      expect(searchHistory.value.length).toBe(0)

      // 5. 键盘按 Tab 键可平滑收起历史浮层
      searchInput.value = '测试项'
      commitSearchHistory()
      expect(searchHistory.value.length).toBe(1)
      searchInput.value = ''
      await nextTick()

      onSearchKeydown(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
      expect(isHistoryOpen.value).toBe(true)

      onSearchKeydown(new KeyboardEvent('keydown', { key: 'Tab' }))
      expect(isHistoryOpen.value).toBe(false)
    })
    scope.stop()
  })

  it('synchronizes searchScope and shelfScope when switching commands', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const shelfSearch = ref('')
      const shelfScope = ref<'all' | 'id' | 'author' | 'tag'>('all')

      const {
        searchInput,
        searchActiveCommand,
        searchScope,
        handleSelectCommand,
        handleClearCommand,
      } = useShelfSearch({
        activeSource: computed(() => ''),
        shelfSearch,
        shelfScope,
        filteredItems: computed(() => []),
        allItems: computed(() => []),
        router: { push: vi.fn<() => Promise<void>>() } as unknown as Router,
        toast: vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => number>(),
      })

      // Default: all
      expect(searchScope.value).toBe('all')
      expect(shelfScope.value).toBe('all')

      // 1. Select /author
      handleSelectCommand({
        id: 'author',
        name: '/作者',
        label: '作者',
        icon: 'users',
        aliases: ['a'],
        description: '作者筛选',
        placeholder: '输入作者',
      })
      await nextTick()
      expect(searchActiveCommand.value).toBe('author')
      expect(searchScope.value).toBe('author')

      searchInput.value = '水龙敬'
      await nextTick()
      expect(shelfSearch.value).toBe('水龙敬')
      expect(shelfScope.value).toBe('author')

      // 2. Select /tag
      handleSelectCommand({
        id: 'tag',
        name: '/标签',
        label: '标签',
        icon: 'tag',
        aliases: ['tag'],
        description: '标签筛选',
        placeholder: '输入标签',
      })
      await nextTick()
      expect(searchActiveCommand.value).toBe('tag')
      expect(searchScope.value).toBe('tag')

      searchInput.value = '纯爱'
      await nextTick()
      expect(shelfSearch.value).toBe('纯爱')
      expect(shelfScope.value).toBe('tag')

      // 3. Clear command
      handleClearCommand()
      await nextTick()
      expect(searchActiveCommand.value).toBeNull()
      expect(searchScope.value).toBe('all')
      expect(shelfScope.value).toBe('all')
    })
    scope.stop()
  })
})

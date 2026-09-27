/**
 * @file useShelfSearch.ts
 * @description 书架搜索栏联动、快捷指令、分镜台词检索与搜索历史顶层编排 Composable。
 *
 * 核心职责：
 * 1. 意图分流与状态解耦：台词搜索模式冻结书架常规过滤，常规搜索模式清空台词 FTS 状态；
 * 2. 编排快捷指令选单 (`useSearchCommands`)、台词检索浮层 (`useDialogueSearch`) 与搜索历史 (`useSearchHistory`)；
 * 3. 集中调度键盘事件（WAI-ARIA Combobox / Listbox 导航、IME 组合保护、阶梯式 Escape 退出）；
 * 4. 封装聚焦、失焦与外部点击关闭 (onClickOutside) 逻辑，彻底下沉视图胶水代码；
 * 5. 跨路由会话级状态保持：无缝恢复退出前的检索词与指令模式，杜绝被空值误重置。
 */

import { computed, nextTick, ref, watch, type ComputedRef, type Ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import type { Router } from 'vue-router'
import {
  useSearchCommands,
  AVAILABLE_COMMANDS,
  type SearchCommandDef,
  type SearchCommandType,
} from '@/composables/useSearchCommands'
import { useDialogueSearch } from '@/composables/useDialogueSearch'
import { useSearchHistory, type SearchHistoryItem } from '@/composables/useSearchHistory'
import type { SearchScope } from '@/composables/useLibraryFilter'
import type { DialogueSearchItem, LibrarySummary } from '@/types'

export interface UseShelfSearchOptions {
  /** 当前选中的数据源过滤 (如 'jm' | 'picacg' | 'local') */
  activeSource: ComputedRef<string>
  /** 书架网格常规过滤关键词 Ref */
  shelfSearch: Ref<string>
  /** 当前激活的检索范围限制 Ref */
  shelfScope?: Ref<SearchScope>
  /** 当前激活的快捷指令模式 Ref（用于跨路由会话保持） */
  shelfCommand?: Ref<SearchCommandType | null>
  /** 当前已过滤的藏书列表（供随机抽选使用） */
  filteredItems: ComputedRef<LibrarySummary[]>
  /** 书库全量藏书列表（供随机抽选备用） */
  allItems: ComputedRef<LibrarySummary[]>
  /** 路由实例 */
  router: Router
  /** 消息气泡通知方法 */
  toast: (msg: string, tone?: 'info' | 'error' | 'success') => unknown
  /** 外部传入的搜索容器 DOM 引用（如通过 Vue 3.5 useTemplateRef 获取） */
  searchContainerRef?: Readonly<Ref<HTMLElement | null>> | Ref<HTMLElement | null>
  /** 外部传入的搜索输入框 DOM 引用（如通过 Vue 3.5 useTemplateRef 获取） */
  searchInputRef?: Readonly<Ref<HTMLInputElement | null>> | Ref<HTMLInputElement | null>
}

export interface UseShelfSearchReturn {
  /** 搜索容器 DOM 引用（用于浮层与点击外部检测） */
  searchContainerRef: Readonly<Ref<HTMLElement | null>> | Ref<HTMLElement | null>
  /** 搜索输入框 DOM 引用 */
  searchInputRef: Readonly<Ref<HTMLInputElement | null>> | Ref<HTMLInputElement | null>
  /** 搜索输入框双向绑定的原始文本 */
  searchInput: Ref<string>
  /** 当前激活的快捷指令模式（null 为常规搜索） */
  searchActiveCommand: Ref<SearchCommandType | null>
  /** 当前生效的检索范围限定 */
  searchScope: ComputedRef<SearchScope>
  /** 搜索框动态占位文案 */
  searchPlaceholder: Ref<string>
  /** 快捷指令选单是否展开 */
  isCommandMenuOpen: Ref<boolean>
  /** 快捷指令选单当前键盘高亮索引 */
  commandMenuFocusedIndex: Ref<number>
  /** 匹配当前输入的快捷指令候选集 */
  commandFilteredCommands: Ref<SearchCommandDef[]>
  /** 台词检索浮层是否展开 */
  isDialogueOpen: Ref<boolean>
  /** 命中的台词搜索结果集 */
  dialogueResults: Ref<DialogueSearchItem[]>
  /** 命中的台词总条数 */
  dialogueTotal: Ref<number>
  /** 是否正在执行台词检索 */
  isDialogueSearching: Ref<boolean>
  /** 台词检索异常信息 */
  dialogueError: Ref<string>
  /** 当前台词检索关键词 */
  dialogueQuery: Ref<string>
  /** 台词结果列表键盘高亮索引 */
  dialogueFocusedIndex: Ref<number>
  /**
   * 台词结果 listbox 此刻是否真的渲染着（浮层展开、不在检索、无错且有结果）。
   * 输入框的 aria-expanded 与 aria-controls 据此成对设置，免得指向不存在的节点
   */
  isDialogueListboxShown: ComputedRef<boolean>
  /** 搜索历史选单是否展开 */
  isHistoryOpen: Ref<boolean>
  /** 搜索历史当前键盘高亮索引 */
  historyFocusedIndex: Ref<number>
  /** 搜索历史列表数据 */
  searchHistory: Ref<SearchHistoryItem[]>
  /** 搜索历史 listbox 此刻是否渲染（历史展开、无指令选单、无台词浮层、有历史项且输入框为空） */
  isHistoryListboxShown: ComputedRef<boolean>
  /** Combobox 整体是否处于展开态（快捷指令 / 台词列表 / 搜索历史 任一浮层处于渲染展开态） */
  isComboboxExpanded: ComputedRef<boolean>
  /** 当前激活的 Combobox 下拉容器 DOM ID（未展开时为 undefined） */
  activeComboboxControls: ComputedRef<string | undefined>
  /** 当前激活的 Combobox 选项 DOM ID（未激活时为 undefined） */
  activeComboboxActivedescendant: ComputedRef<string | undefined>
  /** 选中特定快捷指令 */
  handleSelectCommand: (cmd: SearchCommandDef) => void
  /** 清除当前指令胶囊切回常规搜索 */
  handleClearCommand: () => void
  /** 关闭快捷指令选单 */
  closeCommandMenu: () => void
  /** 关闭台词检索浮层 */
  closeDialogueSearch: () => void
  /** 选中特定搜索历史项 */
  handleSelectHistory: (item: SearchHistoryItem) => void
  /** 移除指定历史项 */
  handleRemoveHistory: (id: string) => void
  /** 清空全部搜索历史 */
  handleClearHistory: () => void
  /** 关闭搜索历史浮层 */
  closeHistory: () => void
  /** 显式提交当前搜索关键词入历史（回车或点击漫画卡片时触发） */
  commitSearchHistory: () => void
  /** 搜索框获取焦点交互 */
  onSearchFocus: () => void
  /** 搜索框全局键盘交互事件分流 */
  onSearchKeydown: (e: KeyboardEvent) => void
  /** 跳转至命中台词的目标分镜画页 */
  navigateToResult: (item: DialogueSearchItem, routerInstance?: Router) => void
}

export function useShelfSearch(options: UseShelfSearchOptions): UseShelfSearchReturn {
  const { activeSource, shelfSearch, filteredItems, allItems, router, toast } = options

  const searchContainerRef = options.searchContainerRef ?? ref<HTMLElement | null>(null)
  const searchInputRef = options.searchInputRef ?? ref<HTMLInputElement | null>(null)

  const { history: searchHistory, addHistory, removeHistory, clearHistory } = useSearchHistory()
  const isHistoryOpen = ref(false)
  const historyFocusedIndex = ref(0)

  const openHistory = () => {
    if (
      searchHistory.value.length > 0 &&
      !searchInput.value.trim() &&
      searchActiveCommand.value === null
    ) {
      isHistoryOpen.value = true
      historyFocusedIndex.value = 0
    }
  }

  const closeHistory = () => {
    isHistoryOpen.value = false
    historyFocusedIndex.value = 0
  }

  const {
    query: dialogueQuery,
    results: dialogueResults,
    total: dialogueTotal,
    isSearching: isDialogueSearching,
    error: dialogueError,
    isOpen: isDialogueOpen,
    focusedIndex: dialogueFocusedIndex,
    executeSearch: executeDialogueSearch,
    open: openDialogueSearch,
    close: closeDialogueSearch,
    navigateNext: nextDialogueResult,
    navigatePrev: prevDialogueResult,
    navigateToResult: rawNavigateToResult,
  } = useDialogueSearch({ source: activeSource })

  // 与 DialogueSearchPopover 的 v-if 链同一判据：仅在无错且结果存在时渲染 listbox（刷新检索期间仍保留）
  const isDialogueListboxShown = computed(
    () => isDialogueOpen.value && !dialogueError.value && dialogueResults.value.length > 0,
  )

  const isHistoryListboxShown = computed(
    () =>
      isHistoryOpen.value &&
      searchHistory.value.length > 0 &&
      !isCommandMenuOpen.value &&
      !isDialogueOpen.value &&
      !searchInput.value.trim() &&
      searchActiveCommand.value === null,
  )

  const commitSearchHistory = () => {
    const query = searchInput.value.trim()
    if (query && (searchActiveCommand.value !== null || !query.startsWith('/'))) {
      addHistory(query, searchActiveCommand.value)
    }
  }

  const navigateToResult = (item: DialogueSearchItem, routerInstance?: Router) => {
    commitSearchHistory()
    rawNavigateToResult(item, routerInstance || router)
  }

  const {
    rawInput: searchInput,
    activeCommand: searchActiveCommand,
    isMenuOpen: isCommandMenuOpen,
    menuFocusedIndex: commandMenuFocusedIndex,
    filteredCommands: commandFilteredCommands,
    currentPlaceholder: searchPlaceholder,
    selectCommand,
    clearCommand,
    openMenu: openCommandMenu,
    closeMenu: closeCommandMenu,
    handleKeydown: handleCommandKeydown,
  } = useSearchCommands({
    initialInput: shelfSearch.value,
    activeCommand: options.shelfCommand,
    isDropdownOpen: computed(() => isDialogueOpen.value || isHistoryOpen.value),
    onRandom: () => {
      const list = filteredItems.value.length > 0 ? filteredItems.value : allItems.value || []
      if (list.length === 0) {
        toast('书架暂无藏书可供抽取', 'info')
        return
      }
      const picked = list[Math.floor(Math.random() * list.length)]
      if (picked) {
        toast(`随手翻得一卷：《${picked.title}》`, 'success')
        void router.push(
          `/comic/${encodeURIComponent(picked.source)}/${encodeURIComponent(picked.source_id)}`,
        )
      }
    },
  })

  const isComboboxExpanded = computed(
    () => isCommandMenuOpen.value || isDialogueListboxShown.value || isHistoryListboxShown.value,
  )

  const activeComboboxControls = computed<string | undefined>(() => {
    if (isCommandMenuOpen.value) return 'search-command-menu'
    if (isDialogueListboxShown.value) return 'dialogue-search-listbox'
    if (isHistoryListboxShown.value) return 'search-history-menu'
    return undefined
  })

  const activeComboboxActivedescendant = computed<string | undefined>(() => {
    if (isCommandMenuOpen.value && commandFilteredCommands.value.length > 0) {
      return `cmd-opt-${commandMenuFocusedIndex.value}`
    }
    if (isDialogueListboxShown.value && dialogueFocusedIndex.value >= 0) {
      return `dialogue-opt-${dialogueFocusedIndex.value}`
    }
    if (isHistoryListboxShown.value && historyFocusedIndex.value >= 0) {
      return `history-opt-${historyFocusedIndex.value}`
    }
    return undefined
  })

  const searchScope = computed<SearchScope>(() => {
    if (searchActiveCommand.value === 'id') return 'id'
    if (searchActiveCommand.value === 'author') return 'author'
    if (searchActiveCommand.value === 'tag') return 'tag'
    return 'all'
  })

  // 意图分流与状态解耦：
  // 1. 台词专注模式：dialogueQuery 接收输入，书架常规 search 强制置空（保持书架网格 100% 冻结，不影响列表）；
  // 2. 键入 '/' 且未成命令：书架 search 保持空（防误过滤）；
  // 3. 常规搜索模式：search 接收 searchInput 驱动书架过滤，dialogueQuery 强制置空（避免多余 FTS 检索）。
  watch(
    [searchInput, searchActiveCommand],
    ([inputVal, cmdVal]) => {
      if (cmdVal === 'dialogue') {
        dialogueQuery.value = inputVal
        shelfSearch.value = ''
        if (options.shelfScope) {
          options.shelfScope.value = 'all'
        }
        if (inputVal.trim()) {
          openDialogueSearch()
        } else {
          closeDialogueSearch()
        }
      } else {
        dialogueQuery.value = ''
        closeDialogueSearch()
        if (inputVal.startsWith('/')) {
          shelfSearch.value = ''
          if (options.shelfScope) {
            options.shelfScope.value = 'all'
          }
          openCommandMenu()
        } else {
          closeCommandMenu()
          shelfSearch.value = inputVal
          if (options.shelfScope) {
            options.shelfScope.value = searchScope.value
          }
        }
      }
      if (inputVal.trim()) {
        closeHistory()
      } else if (
        cmdVal === null &&
        searchInputRef.value &&
        typeof document !== 'undefined' &&
        document.activeElement === searchInputRef.value &&
        searchHistory.value.length > 0
      ) {
        openHistory()
      }
    },
    { immediate: true },
  )

  function handleSelectCommand(cmd: SearchCommandDef) {
    selectCommand(cmd)
    closeHistory()
    void nextTick(() => {
      searchInputRef.value?.focus()
    })
  }

  function handleClearCommand() {
    clearCommand()
    void nextTick(() => {
      searchInputRef.value?.focus()
    })
  }

  function handleSelectHistory(item: SearchHistoryItem) {
    closeHistory()
    if (item.command) {
      const def = AVAILABLE_COMMANDS.find((c) => c.id === item.command)
      if (def) {
        selectCommand(def)
      } else {
        searchActiveCommand.value = item.command
      }
      searchInput.value = item.query
    } else {
      clearCommand()
      searchInput.value = item.query
    }
    commitSearchHistory()
    void nextTick(() => {
      searchInputRef.value?.focus()
    })
  }

  function handleRemoveHistory(id: string) {
    removeHistory(id)
    if (searchHistory.value.length === 0) {
      closeHistory()
    } else if (historyFocusedIndex.value >= searchHistory.value.length) {
      historyFocusedIndex.value = Math.max(0, searchHistory.value.length - 1)
    }
  }

  function handleClearHistory() {
    clearHistory()
    closeHistory()
  }

  function onSearchFocus() {
    if (searchActiveCommand.value === 'dialogue') {
      if (dialogueQuery.value.trim()) {
        openDialogueSearch()
      }
    } else if (searchInput.value.startsWith('/')) {
      openCommandMenu()
    } else if (
      !searchInput.value.trim() &&
      searchActiveCommand.value === null &&
      searchHistory.value.length > 0
    ) {
      openHistory()
    }
  }

  onClickOutside(searchContainerRef, () => {
    closeDialogueSearch()
    closeCommandMenu()
    closeHistory()
  })

  function onSearchKeydown(e: KeyboardEvent) {
    if (handleCommandKeydown(e)) {
      return
    }

    // 搜索历史浮层键盘交互
    if (isHistoryOpen.value && isHistoryListboxShown.value) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        if (searchHistory.value.length > 0) {
          if (historyFocusedIndex.value < searchHistory.value.length - 1) {
            historyFocusedIndex.value++
          } else {
            historyFocusedIndex.value = 0
          }
        }
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        if (searchHistory.value.length > 0) {
          if (historyFocusedIndex.value > 0) {
            historyFocusedIndex.value--
          } else {
            historyFocusedIndex.value = searchHistory.value.length - 1
          }
        }
        return
      }
      if (e.key === 'Delete') {
        const item = searchHistory.value[historyFocusedIndex.value]
        if (item) {
          e.preventDefault()
          handleRemoveHistory(item.id)
        }
        return
      }
      if (e.key === 'Enter') {
        const item = searchHistory.value[historyFocusedIndex.value]
        if (item) {
          e.preventDefault()
          handleSelectHistory(item)
          return
        }
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        closeHistory()
        return
      }
      if (e.key === 'Tab') {
        closeHistory()
      }
    }

    // 当输入框内容为空且未展开任何浮层时，按下向下方向键可主动唤起历史浮层
    if (
      e.key === 'ArrowDown' &&
      !isHistoryOpen.value &&
      !searchInput.value.trim() &&
      searchActiveCommand.value === null &&
      searchHistory.value.length > 0
    ) {
      e.preventDefault()
      openHistory()
      return
    }

    if (e.key === 'Enter' && !e.isComposing) {
      commitSearchHistory()
      closeHistory()
    }

    if (searchActiveCommand.value === 'dialogue' && isDialogueOpen.value) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        nextDialogueResult()
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        prevDialogueResult()
      } else if (e.key === 'Enter') {
        if (dialogueResults.value.length > 0) {
          const targetIndex = dialogueFocusedIndex.value >= 0 ? dialogueFocusedIndex.value : 0
          const targetItem = dialogueResults.value[targetIndex]
          if (targetItem) {
            e.preventDefault()
            navigateToResult(targetItem, router)
          }
        } else if (dialogueQuery.value.trim().length >= 2) {
          e.preventDefault()
          void executeDialogueSearch()
        }
      } else if (e.key === 'Escape') {
        e.preventDefault()
        closeDialogueSearch()
      }
    }
  }

  return {
    searchContainerRef,
    searchInputRef,
    searchInput,
    searchActiveCommand,
    searchScope,
    searchPlaceholder,
    isCommandMenuOpen,
    commandMenuFocusedIndex,
    commandFilteredCommands,
    isDialogueOpen,
    dialogueResults,
    dialogueTotal,
    isDialogueSearching,
    dialogueError,
    dialogueQuery,
    dialogueFocusedIndex,
    isDialogueListboxShown,
    isHistoryOpen,
    historyFocusedIndex,
    searchHistory,
    isHistoryListboxShown,
    isComboboxExpanded,
    activeComboboxControls,
    activeComboboxActivedescendant,
    handleSelectCommand,
    handleClearCommand,
    closeCommandMenu,
    closeDialogueSearch,
    handleSelectHistory,
    handleRemoveHistory,
    handleClearHistory,
    closeHistory,
    commitSearchHistory,
    onSearchFocus,
    onSearchKeydown,
    navigateToResult,
  }
}

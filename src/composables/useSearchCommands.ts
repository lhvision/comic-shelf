/**
 * @file useSearchCommands.ts
 * @description 首页搜索框快捷指令分发与命令胶囊 Composable。
 *
 * 核心特性：
 * 1. 语法拦截：检测以 '/' 开头的输入，展开水墨快捷指令选单；
 * 2. 状态胶囊化：选中指令后将输入框切换为命令胶囊（Command Chip）专注模式；
 * 3. 意图解耦：在台词搜索模式下，书架藏书本地过滤保持冻结，根治“一打台词列表全空”问题；
 * 4. 严密键盘契约：支持 ↑/↓ 导航、Enter/Tab 快捷补全、退格秒级退出胶囊模式。
 */

import { computed, ref, type Ref } from 'vue'

export type SearchCommandType = 'dialogue' | 'id' | 'author' | 'random'

export interface SearchCommandDef {
  id: SearchCommandType
  name: string
  label: string
  icon: string
  aliases: string[]
  description: string
  placeholder: string
  isAction?: boolean
}

export const AVAILABLE_COMMANDS: SearchCommandDef[] = [
  {
    id: 'dialogue',
    name: '/台词',
    label: '台词',
    icon: 'message-square',
    aliases: ['d', 't', 'dialogue', '台词', 'dc'],
    description: '检索分镜台词对白并直达画页分镜气泡',
    placeholder: '检索分镜（至少2字）…',
  },
  {
    id: 'id',
    name: '/车号',
    label: '车号',
    icon: 'book-open',
    aliases: ['id', 'c', 'chehao', '车号', 'jm'],
    description: '按作品编号或车号精确匹配藏书',
    placeholder: '输入作品车号…',
  },
  {
    id: 'author',
    name: '/作者',
    label: '作者',
    icon: 'users',
    aliases: ['a', 'zuozhe', '作者', 'aut'],
    description: '按作者姓名或社团筛选藏书',
    placeholder: '输入作者姓名…',
  },
  {
    id: 'random',
    name: '/随机',
    label: '随机',
    icon: 'refresh',
    aliases: ['r', 'random', 'suiji', '随机', '随手翻', '抽一本'],
    description: '随手翻一本：从在读或未读藏书中随手翻阅一本',
    placeholder: '',
    isAction: true,
  },
]

export interface UseSearchCommandsOptions {
  onRandom?: () => void
  /**
   * 关联外部浮层开闭状态探测。若外部浮层当前处于展开态，
   * Escape 键将优先让外部先关闭浮层，而不抢占销毁命令胶囊。
   */
  isDropdownOpen?: Ref<boolean>
}

export interface UseSearchCommandsReturn {
  rawInput: Ref<string>
  activeCommand: Ref<SearchCommandType | null>
  isMenuOpen: Ref<boolean>
  menuFocusedIndex: Ref<number>
  filteredCommands: Ref<SearchCommandDef[]>
  currentPlaceholder: Ref<string>
  effectiveShelfSearch: Ref<string>
  selectCommand: (cmd: SearchCommandDef) => void
  clearCommand: () => void
  openMenu: () => void
  closeMenu: () => void
  navigateNext: () => void
  navigatePrev: () => void
  handleKeydown: (e: KeyboardEvent) => boolean
}

export function useSearchCommands(options: UseSearchCommandsOptions = {}): UseSearchCommandsReturn {
  const rawInput = ref('')
  const activeCommand = ref<SearchCommandType | null>(null)
  const isMenuOpen = ref(false)
  const menuFocusedIndex = ref(0)

  const filteredCommands = computed(() => {
    const val = rawInput.value.trim()
    if (!val.startsWith('/')) {
      return AVAILABLE_COMMANDS
    }
    const token = val.slice(1).trim().toLowerCase()
    if (!token) {
      return AVAILABLE_COMMANDS
    }
    return AVAILABLE_COMMANDS.filter((cmd) => {
      if (cmd.name.slice(1).toLowerCase().includes(token)) return true
      if (cmd.label.toLowerCase().includes(token)) return true
      return cmd.aliases.some((alias) => alias.toLowerCase().includes(token))
    })
  })

  const currentPlaceholder = computed(() => {
    if (activeCommand.value) {
      const activeDef = AVAILABLE_COMMANDS.find((c) => c.id === activeCommand.value)
      return activeDef?.placeholder ?? '输入关键词检索…'
    }
    return '标题 / 车号 / 作者 / 标签 · 输入 / 提示快捷命令'
  })

  /**
   * 书架底层网格实际接收到的过滤检索词：
   * 1. 常规模式：即原始输入 rawInput；
   * 2. 台词模式：强制返回空字符串 ''，冻结书架网格过滤，彻底消除“一打台词列表全空”；
   * 3. 车号/作者模式：传递 rawInput 进行精确过滤。
   */
  const effectiveShelfSearch = computed(() => {
    if (activeCommand.value === 'dialogue') {
      return ''
    }
    if (rawInput.value.startsWith('/')) {
      return ''
    }
    return rawInput.value
  })

  const selectCommand = (cmd: SearchCommandDef) => {
    isMenuOpen.value = false
    menuFocusedIndex.value = 0

    if (cmd.isAction) {
      rawInput.value = ''
      if (cmd.id === 'random' && options.onRandom) {
        options.onRandom()
      }
      return
    }

    activeCommand.value = cmd.id
    rawInput.value = ''
  }

  const clearCommand = () => {
    activeCommand.value = null
    rawInput.value = ''
    isMenuOpen.value = false
    menuFocusedIndex.value = 0
  }

  const openMenu = () => {
    if (rawInput.value.startsWith('/')) {
      isMenuOpen.value = true
      menuFocusedIndex.value = 0
    }
  }

  const closeMenu = () => {
    isMenuOpen.value = false
    menuFocusedIndex.value = 0
  }

  const navigateNext = () => {
    if (filteredCommands.value.length === 0) return
    if (menuFocusedIndex.value < filteredCommands.value.length - 1) {
      menuFocusedIndex.value++
    } else {
      menuFocusedIndex.value = 0
    }
  }

  const navigatePrev = () => {
    if (filteredCommands.value.length === 0) return
    if (menuFocusedIndex.value > 0) {
      menuFocusedIndex.value--
    } else {
      menuFocusedIndex.value = filteredCommands.value.length - 1
    }
  }

  /**
   * 处理搜索框键盘事件，返回 true 表示已被指令系统拦截处理
   */
  const handleKeydown = (e: KeyboardEvent): boolean => {
    // 关键防线：若当前正处于输入法（IME）组合字合成状态，绝不拦截任何键盘事件
    if (e.isComposing || e.keyCode === 229) {
      return false
    }

    // 1. 若当前命令菜单展开
    if (isMenuOpen.value) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        navigateNext()
        return true
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        navigatePrev()
        return true
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        const selected = filteredCommands.value[menuFocusedIndex.value]
        if (selected) {
          selectCommand(selected)
        }
        return true
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        closeMenu()
        return true
      }
      if (e.key === ' ') {
        // 空格快捷确认首选匹配
        const selected = filteredCommands.value[menuFocusedIndex.value]
        if (selected && rawInput.value.trim().length > 1) {
          e.preventDefault()
          selectCommand(selected)
          return true
        }
      }
    }

    // 2. 若当前已处于命令胶囊模式（如台词模式）
    if (activeCommand.value !== null) {
      // 当输入框内容为空且按下退格键时，退出命令模式切回常规搜索
      if (e.key === 'Backspace' && rawInput.value === '') {
        e.preventDefault()
        clearCommand()
        return true
      }
      if (e.key === 'Escape') {
        // 阶梯式退出（Cascading Dismiss）第一级：
        // 若外部关联浮层处于展开态，放行让外部先关闭浮层（不抢占）
        if (options?.isDropdownOpen?.value) {
          return false
        }
        // 阶梯式退出第二级：若输入框仍有文本，先清空当前输入的文本
        if (rawInput.value !== '') {
          e.preventDefault()
          rawInput.value = ''
          return true
        }
        // 阶梯式退出第三级：输入框已空且无浮层，退出命令胶囊模式
        e.preventDefault()
        clearCommand()
        return true
      }
    }

    // 3. 用户在常规输入模式下键入 '/'
    if (!activeCommand.value && e.key === '/' && rawInput.value === '') {
      isMenuOpen.value = true
      menuFocusedIndex.value = 0
    }

    return false
  }

  return {
    rawInput,
    activeCommand,
    isMenuOpen,
    menuFocusedIndex,
    filteredCommands,
    currentPlaceholder,
    effectiveShelfSearch,
    selectCommand,
    clearCommand,
    openMenu,
    closeMenu,
    navigateNext,
    navigatePrev,
    handleKeydown,
  }
}

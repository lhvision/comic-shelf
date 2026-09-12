import { describe, it, expect, vi } from 'vite-plus/test'
import { effectScope, ref } from 'vue'
import { useSearchCommands, AVAILABLE_COMMANDS } from '@/composables/useSearchCommands'

describe('useSearchCommands', () => {
  it('initializes with default empty state', () => {
    const scope = effectScope()
    scope.run(() => {
      const { rawInput, activeCommand, isMenuOpen, menuFocusedIndex, effectiveShelfSearch } =
        useSearchCommands()

      expect(rawInput.value).toBe('')
      expect(activeCommand.value).toBeNull()
      expect(isMenuOpen.value).toBe(false)
      expect(menuFocusedIndex.value).toBe(0)
      expect(effectiveShelfSearch.value).toBe('')
    })
    scope.stop()
  })

  it('filters commands when typing slash token', () => {
    const scope = effectScope()
    scope.run(() => {
      const { rawInput, filteredCommands } = useSearchCommands()

      rawInput.value = '/'
      expect(filteredCommands.value.length).toBe(AVAILABLE_COMMANDS.length)

      rawInput.value = '/d'
      expect(filteredCommands.value.some((c) => c.id === 'dialogue')).toBe(true)

      rawInput.value = '/作者'
      expect(filteredCommands.value.length).toBe(1)
      expect(filteredCommands.value[0]?.id).toBe('author')
    })
    scope.stop()
  })

  it('switches to dialogue command chip and freezes shelf filter', () => {
    const scope = effectScope()
    scope.run(() => {
      const { rawInput, activeCommand, effectiveShelfSearch, selectCommand, clearCommand } =
        useSearchCommands()

      const dialogueCmd = AVAILABLE_COMMANDS.find((c) => c.id === 'dialogue')!
      selectCommand(dialogueCmd)

      expect(activeCommand.value).toBe('dialogue')
      expect(rawInput.value).toBe('')
      // 核心断言：台词模式下，书架接收到的搜索词必须始终为空字符串，彻底冻结网格过滤
      expect(effectiveShelfSearch.value).toBe('')

      rawInput.value = '最后的波纹'
      expect(effectiveShelfSearch.value).toBe('')

      clearCommand()
      expect(activeCommand.value).toBeNull()
      expect(rawInput.value).toBe('')
    })
    scope.stop()
  })

  it('exits command chip mode on Backspace when input is empty', () => {
    const scope = effectScope()
    scope.run(() => {
      const { activeCommand, selectCommand, handleKeydown } = useSearchCommands()

      const dialogueCmd = AVAILABLE_COMMANDS.find((c) => c.id === 'dialogue')!
      selectCommand(dialogueCmd)
      expect(activeCommand.value).toBe('dialogue')

      // 输入框为空时按 Backspace
      const prevented = handleKeydown({
        key: 'Backspace',
        preventDefault: vi.fn<() => void>(),
      } as unknown as KeyboardEvent)

      expect(prevented).toBe(true)
      expect(activeCommand.value).toBeNull()
    })
    scope.stop()
  })

  it('triggers onRandom callback for random action command', () => {
    const onRandom = vi.fn<() => void>()
    const scope = effectScope()
    scope.run(() => {
      const { selectCommand, activeCommand, rawInput } = useSearchCommands({ onRandom })

      const randomCmd = AVAILABLE_COMMANDS.find((c) => c.id === 'random')!
      selectCommand(randomCmd)

      expect(onRandom).toHaveBeenCalledTimes(1)
      expect(activeCommand.value).toBeNull()
      expect(rawInput.value).toBe('')
    })
    scope.stop()
  })

  it('does not intercept keyboard events during IME composition', () => {
    const scope = effectScope()
    scope.run(() => {
      const { rawInput, isMenuOpen, handleKeydown } = useSearchCommands()
      rawInput.value = '/t'
      isMenuOpen.value = true

      // 正在输入法组合字合成中 (isComposing = true)
      const prevented = handleKeydown({
        key: 'Enter',
        isComposing: true,
        preventDefault: vi.fn<() => void>(),
      } as unknown as KeyboardEvent)

      expect(prevented).toBe(false)

      // 微软拼音等 keyCode 229 合成状态
      const prevented229 = handleKeydown({
        key: 'ArrowDown',
        keyCode: 229,
        preventDefault: vi.fn<() => void>(),
      } as unknown as KeyboardEvent)

      expect(prevented229).toBe(false)
    })
    scope.stop()
  })

  it('handles cascading Escape dismiss properly', () => {
    const scope = effectScope()
    scope.run(() => {
      const isDropdownOpen = ref(true)
      const { activeCommand, rawInput, selectCommand, handleKeydown } = useSearchCommands({
        isDropdownOpen,
      })

      const dialogueCmd = AVAILABLE_COMMANDS.find((c) => c.id === 'dialogue')!
      selectCommand(dialogueCmd)
      rawInput.value = '战斗'

      // 第一级：外部浮层处于展开态，Escape 放行给外部浮层关闭
      const res1 = handleKeydown({
        key: 'Escape',
        preventDefault: vi.fn<() => void>(),
      } as unknown as KeyboardEvent)
      expect(res1).toBe(false)
      expect(activeCommand.value).toBe('dialogue')
      expect(rawInput.value).toBe('战斗')

      // 外部浮层已关闭
      isDropdownOpen.value = false

      // 第二级：输入框仍有文字，Escape 仅清空文本，保留命令胶囊
      const res2 = handleKeydown({
        key: 'Escape',
        preventDefault: vi.fn<() => void>(),
      } as unknown as KeyboardEvent)
      expect(res2).toBe(true)
      expect(activeCommand.value).toBe('dialogue')
      expect(rawInput.value).toBe('')

      // 第三级：输入框已空且无浮层，Escape 退出命令胶囊模式
      const res3 = handleKeydown({
        key: 'Escape',
        preventDefault: vi.fn<() => void>(),
      } as unknown as KeyboardEvent)
      expect(res3).toBe(true)
      expect(activeCommand.value).toBeNull()
    })
    scope.stop()
  })
})

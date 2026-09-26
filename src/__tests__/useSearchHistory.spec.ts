import { describe, it, expect, beforeEach } from 'vite-plus/test'
import {
  useSearchHistory,
  SEARCH_HISTORY_KEY,
  MAX_SEARCH_HISTORY,
} from '@/composables/useSearchHistory'

describe('useSearchHistory', () => {
  beforeEach(() => {
    localStorage.removeItem(SEARCH_HISTORY_KEY)
    const { clearHistory } = useSearchHistory()
    clearHistory()
  })

  it('uses standard comic-shelf key convention', () => {
    expect(SEARCH_HISTORY_KEY).toBe('comic-shelf:search-history:v1')
  })

  it('initializes with empty history', () => {
    const { history } = useSearchHistory()
    expect(history.value).toEqual([])
  })

  it('adds history items and trims whitespace', () => {
    const { history, addHistory } = useSearchHistory()

    addHistory('  东方Project  ')
    expect(history.value.length).toBe(1)
    expect(history.value[0]?.query).toBe('东方Project')
    expect(history.value[0]?.command).toBeNull()

    // 空字符串被安全忽略
    addHistory('   ')
    expect(history.value.length).toBe(1)
  })

  it('records slash commands with arguments', () => {
    const { history, addHistory } = useSearchHistory()

    addHistory('不要啊', 'dialogue')
    expect(history.value.length).toBe(1)
    expect(history.value[0]?.query).toBe('不要啊')
    expect(history.value[0]?.command).toBe('dialogue')

    addHistory('水龙敬', 'author')
    expect(history.value.length).toBe(2)
    expect(history.value[0]?.query).toBe('水龙敬')
    expect(history.value[0]?.command).toBe('author')
  })

  it('ignores random action command', () => {
    const { history, addHistory } = useSearchHistory()

    addHistory('随手翻', 'random')
    expect(history.value.length).toBe(0)
  })

  it('deduplicates and bumps to top (LRU behavior)', () => {
    const { history, addHistory } = useSearchHistory()

    addHistory('纯爱')
    addHistory('牛头人')
    addHistory('纯爱')

    expect(history.value.length).toBe(2)
    expect(history.value[0]?.query).toBe('纯爱')
    expect(history.value[1]?.query).toBe('牛头人')

    // 同名不同命令视为不同历史项
    addHistory('纯爱', 'dialogue')
    expect(history.value.length).toBe(3)
    expect(history.value[0]?.query).toBe('纯爱')
    expect(history.value[0]?.command).toBe('dialogue')
  })

  it('strictly caps at MAX_SEARCH_HISTORY (8 items)', () => {
    const { history, addHistory } = useSearchHistory()

    for (let i = 1; i <= 12; i++) {
      addHistory(`关键词 ${i}`)
    }

    expect(history.value.length).toBe(MAX_SEARCH_HISTORY)
    expect(history.value[0]?.query).toBe('关键词 12')
    expect(history.value[MAX_SEARCH_HISTORY - 1]?.query).toBe('关键词 5')
  })

  it('removes single item by ID and clears all', () => {
    const { history, addHistory, removeHistory, clearHistory } = useSearchHistory()

    addHistory('项一')
    addHistory('项二')
    const itemToRemove = history.value.find((item) => item.query === '项一')!
    expect(itemToRemove).toBeDefined()

    removeHistory(itemToRemove.id)
    expect(history.value.length).toBe(1)
    expect(history.value[0]?.query).toBe('项二')

    clearHistory()
    expect(history.value.length).toBe(0)
  })

  it('truncates excessively long queries to MAX_QUERY_LENGTH (100)', () => {
    const { history, addHistory } = useSearchHistory()

    const hugeQuery = 'a'.repeat(250)
    addHistory(hugeQuery)

    expect(history.value.length).toBe(1)
    expect(history.value[0]?.query.length).toBe(100)
    expect(history.value[0]?.query).toBe('a'.repeat(100))
  })

  it('gracefully recovers when localStorage contains non-array corrupted data or bad items', () => {
    const { history, addHistory } = useSearchHistory()

    // 模拟脏数据写入非数组
    ;(history as unknown as { value: unknown }).value = { corrupted: true }

    addHistory('正常关键词')
    expect(Array.isArray(history.value)).toBe(true)
    expect(history.value.length).toBe(1)
    expect(history.value[0]?.query).toBe('正常关键词')

    // 模拟数组中混入 null、数字、缺失必要字段、NaN 时间戳或非法指令对象的伪造对象
    ;(history as unknown as { value: unknown }).value = [
      null,
      123,
      { id: '1', missingQuery: true },
      { id: 'bad-nan', query: '无效时间戳', timestamp: NaN },
      { id: 'bad-cmd', query: '非法指令对象', timestamp: 12345, command: { fake: true } },
      { id: 'good', query: '完好数据', timestamp: 12345 },
    ]

    addHistory('新写入项')
    expect(history.value.length).toBe(2)
    expect(history.value[0]?.query).toBe('新写入项')
    expect(history.value[1]?.query).toBe('完好数据')
  })

  it('ignores slash command prefixes when no command is active', () => {
    const { history, addHistory } = useSearchHistory()

    addHistory('/')
    expect(history.value.length).toBe(0)

    addHistory('/unknown_cmd')
    expect(history.value.length).toBe(0)

    // 当 command 明确激活时，即使 query 包含前缀也不受拦截
    addHistory('/车号测试', 'id')
    expect(history.value.length).toBe(1)
    expect(history.value[0]?.query).toBe('/车号测试')
  })

  it('performs case-insensitive deduplication and updates to latest casing', () => {
    const { history, addHistory } = useSearchHistory()

    addHistory('One Piece')
    addHistory('one piece')

    expect(history.value.length).toBe(1)
    expect(history.value[0]?.query).toBe('one piece')
  })
})

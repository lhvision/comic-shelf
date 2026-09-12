import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { effectScope, ref } from 'vue'
import type { Router } from 'vue-router'
import { useDialogueSearch } from '@/composables/useDialogueSearch'
import { api, type RequestOptions } from '@/api/client'
import type { DialogueSearchResponse } from '@/types'

vi.mock('@/api/client', () => ({
  api: {
    searchDialogue:
      vi.fn<
        (
          q: string,
          source?: string,
          limit?: number,
          options?: RequestOptions,
        ) => Promise<DialogueSearchResponse>
      >(),
  },
}))

describe('useDialogueSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with default empty state', () => {
    const scope = effectScope()
    scope.run(() => {
      const { query, results, total, isSearching, error, isOpen, focusedIndex, hasResults } =
        useDialogueSearch()

      expect(query.value).toBe('')
      expect(results.value).toEqual([])
      expect(total.value).toBe(0)
      expect(isSearching.value).toBe(false)
      expect(error.value).toBe('')
      expect(isOpen.value).toBe(false)
      expect(focusedIndex.value).toBe(-1)
      expect(hasResults.value).toBe(false)
    })
    scope.stop()
  })

  it('executes search successfully and updates results and isOpen', async () => {
    const mockResponse: DialogueSearchResponse = {
      results: [
        {
          source: 'jm',
          source_id: '1059521',
          title: '老师请快看这个孩子',
          page_index: 3,
          bubble_id: 1,
          text: '老师请快看这个孩子',
          snippet: '...<mark>老师</mark>请快看这个孩子...',
          box: [0.1, 0.2, 0.3, 0.4],
          lang: 'zh',
          cover: '/covers/jm/1059521.jpg',
        },
      ],
      total: 1,
    }

    vi.mocked(api.searchDialogue).mockResolvedValueOnce(mockResponse)

    const scope = effectScope()
    await scope.run(async () => {
      const source = ref('jm')
      const { executeSearch, results, total, isSearching, isOpen, hasResults } = useDialogueSearch({
        source,
      })

      const searchPromise = executeSearch('老师')
      expect(isSearching.value).toBe(true)

      await searchPromise

      expect(isSearching.value).toBe(false)
      expect(results.value.length).toBe(1)
      expect(results.value[0]?.title).toBe('老师请快看这个孩子')
      expect(total.value).toBe(1)
      expect(isOpen.value).toBe(true)
      expect(hasResults.value).toBe(true)
      expect(api.searchDialogue).toHaveBeenCalledWith('老师', 'jm', 20, expect.any(Object))
    })
    scope.stop()
  })

  it('handles search failure gracefully', async () => {
    vi.mocked(api.searchDialogue).mockRejectedValueOnce(new Error('网络请求异常'))

    const scope = effectScope()
    await scope.run(async () => {
      const { executeSearch, results, error, isSearching } = useDialogueSearch()

      await executeSearch('出错测试')

      expect(isSearching.value).toBe(false)
      expect(results.value).toEqual([])
      expect(error.value).toBe('网络请求异常')
    })
    scope.stop()
  })

  it('supports keyboard navigation (next/prev) and wrapping', () => {
    const scope = effectScope()
    scope.run(() => {
      const { results, focusedIndex, navigateNext, navigatePrev } = useDialogueSearch()

      results.value = [
        { source: 'jm', source_id: '1', title: 'A', page_index: 1, text: 'A', box: [0, 0, 0, 0] },
        { source: 'jm', source_id: '2', title: 'B', page_index: 2, text: 'B', box: [0, 0, 0, 0] },
        { source: 'jm', source_id: '3', title: 'C', page_index: 3, text: 'C', box: [0, 0, 0, 0] },
      ]

      expect(focusedIndex.value).toBe(-1)
      navigateNext()
      expect(focusedIndex.value).toBe(0)
      navigateNext()
      expect(focusedIndex.value).toBe(1)
      navigateNext()
      expect(focusedIndex.value).toBe(2)
      navigateNext()
      expect(focusedIndex.value).toBe(0) // wrap around

      navigatePrev()
      expect(focusedIndex.value).toBe(2) // wrap backward
      navigatePrev()
      expect(focusedIndex.value).toBe(1)
    })
    scope.stop()
  })

  it('navigates to reader with formatted bubble_box and text query parameters', () => {
    const scope = effectScope()
    scope.run(() => {
      const { navigateToResult, isOpen } = useDialogueSearch()
      isOpen.value = true

      const mockRouter = {
        push: vi.fn<(to: unknown) => Promise<unknown>>(),
      }

      const item = {
        source: 'jm',
        source_id: '1059521',
        title: '测试漫画',
        page_index: 5,
        text: '久违的与老师外出',
        box: [0.04571, 0.04689, 0.19972, 0.13751],
      }

      navigateToResult(item, mockRouter as unknown as Router)

      expect(isOpen.value).toBe(false)
      expect(mockRouter.push).toHaveBeenCalledWith({
        path: '/comic/jm/1059521/read/5',
        query: {
          bubble_box: '0.0457,0.0469,0.1997,0.1375',
          bubble_text: '久违的与老师外出',
        },
      })
    })
    scope.stop()
  })
})

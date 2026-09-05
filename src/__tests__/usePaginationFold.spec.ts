import { describe, it, expect, vi } from 'vite-plus/test'
import { ref } from 'vue'
import { usePaginationFold } from '@/composables/usePaginationFold'

describe('usePaginationFold composable', () => {
  it('chunks items by step and computes remaining items', () => {
    const list = ref(Array.from({ length: 25 }, (_, i) => i + 1))
    const { visibleCount, visibleItems, remainingCount, canCollapse, loadMore, loadAll, collapse } =
      usePaginationFold({
        items: list,
        step: 10,
      })

    expect(visibleCount.value).toBe(10)
    expect(visibleItems.value.length).toBe(10)
    expect(remainingCount.value).toBe(15)
    expect(canCollapse.value).toBe(false)

    // Load next step
    loadMore()
    expect(visibleCount.value).toBe(20)
    expect(visibleItems.value.length).toBe(20)
    expect(remainingCount.value).toBe(5)
    expect(canCollapse.value).toBe(true)

    // Load all
    loadAll()
    expect(visibleCount.value).toBe(25)
    expect(visibleItems.value.length).toBe(25)
    expect(remainingCount.value).toBe(0)

    // Collapse
    collapse()
    expect(visibleCount.value).toBe(10)
    expect(visibleItems.value.length).toBe(10)
    expect(remainingCount.value).toBe(15)
    expect(canCollapse.value).toBe(false)
  })

  it('triggers scrollIntoView when collapsing with scrollTarget', async () => {
    const list = ref([1, 2, 3, 4, 5, 6, 7, 8])
    const scrollIntoViewMock = vi.fn<(options?: ScrollIntoViewOptions) => void>()
    const targetEl = ref({
      scrollIntoView: scrollIntoViewMock,
    } as unknown as HTMLElement)

    const { loadMore, collapse } = usePaginationFold({
      items: list,
      step: 3,
      scrollTarget: targetEl,
    })

    loadMore()
    collapse()

    await Promise.resolve()
    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'start',
    })
  })

  it('supports initialStep distinct from step and fires onChange', () => {
    const list = ref(Array.from({ length: 50 }, (_, i) => i))
    const onChangeMock = vi.fn<(count: number) => void>()

    const { visibleCount, canCollapse, loadMore, collapse } = usePaginationFold({
      items: list,
      step: 10,
      initialStep: 20,
      onChange: onChangeMock,
    })

    expect(visibleCount.value).toBe(20)
    expect(canCollapse.value).toBe(false)

    loadMore()
    expect(visibleCount.value).toBe(30)
    expect(canCollapse.value).toBe(true)
    expect(onChangeMock).toHaveBeenCalledWith(30)

    collapse()
    expect(visibleCount.value).toBe(20)
    expect(canCollapse.value).toBe(false)
    expect(onChangeMock).toHaveBeenCalledWith(20)
  })
})

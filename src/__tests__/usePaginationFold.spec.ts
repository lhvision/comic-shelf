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

  it('allows collapsing back to step when initialized with larger initialVisibleCount', () => {
    const list = ref(Array.from({ length: 50 }, (_, i) => i))
    const onChangeMock = vi.fn<(count: number) => void>()

    const { visibleCount, canCollapse, collapse } = usePaginationFold({
      items: list,
      step: 12,
      initialVisibleCount: 36,
      onChange: onChangeMock,
    })

    // Restored at 36, can collapse back to baseline 12
    expect(visibleCount.value).toBe(36)
    expect(canCollapse.value).toBe(true)

    collapse()
    expect(visibleCount.value).toBe(12)
    expect(canCollapse.value).toBe(false)
    expect(onChangeMock).toHaveBeenCalledWith(12)
  })

  it('notifies onChange when reset is called', () => {
    const list = ref(Array.from({ length: 50 }, (_, i) => i))
    const onChangeMock = vi.fn<(count: number) => void>()

    const { visibleCount, reset } = usePaginationFold({
      items: list,
      step: 12,
      onChange: onChangeMock,
    })

    reset(24)
    expect(visibleCount.value).toBe(24)
    expect(onChangeMock).toHaveBeenCalledWith(24)

    reset()
    expect(visibleCount.value).toBe(12)
    expect(onChangeMock).toHaveBeenCalledWith(12)
  })

  it('triggers safety brake at brakeThreshold and allows releasing brake', () => {
    const list = ref(Array.from({ length: 100 }, (_, i) => i))
    const { visibleCount, isBraked, loadMore, releaseBrake, collapse } = usePaginationFold({
      items: list,
      step: 12,
      brakeThreshold: 36,
    })

    expect(visibleCount.value).toBe(12)
    expect(isBraked.value).toBe(false)

    loadMore() // 24
    expect(isBraked.value).toBe(false)

    loadMore() // 36 - hits threshold
    expect(visibleCount.value).toBe(36)
    expect(isBraked.value).toBe(true)

    // Release brake with additional 24
    releaseBrake(24) // visibleCount goes to 48, threshold becomes 36 + 24 = 60
    expect(visibleCount.value).toBe(48)
    expect(isBraked.value).toBe(false)

    loadMore() // 60 - hits new threshold
    expect(visibleCount.value).toBe(60)
    expect(isBraked.value).toBe(true)

    // Collapse resets threshold back to 36
    collapse()
    expect(visibleCount.value).toBe(12)
    expect(isBraked.value).toBe(false)
  })

  it('respects external totalCount for server-side pagination remaining calculation', () => {
    const list = ref(Array.from({ length: 24 }, (_, i) => i))
    const { remainingCount, visibleCount, loadMore } = usePaginationFold({
      items: list,
      step: 12,
      totalCount: 1000,
    })

    expect(visibleCount.value).toBe(12)
    expect(remainingCount.value).toBe(988)

    loadMore()
    expect(visibleCount.value).toBe(24)
    expect(remainingCount.value).toBe(976)
  })

  it('supports maxCap in loadAll with soft cap and tiered unfolding', () => {
    const list = ref(Array.from({ length: 250 }, (_, i) => i))
    const { visibleCount, remainingCount, loadAll } = usePaginationFold({
      items: list,
      step: 12,
    })

    expect(visibleCount.value).toBe(12)

    // First loadAll with cap 120
    loadAll(120)
    expect(visibleCount.value).toBe(120)
    expect(remainingCount.value).toBe(130)

    // Second loadAll with cap 120 steps forward by 120 (to 240)
    loadAll(120)
    expect(visibleCount.value).toBe(240)
    expect(remainingCount.value).toBe(10)

    // Third loadAll finishes remaining items
    loadAll(120)
    expect(visibleCount.value).toBe(250)
    expect(remainingCount.value).toBe(0)
  })
})

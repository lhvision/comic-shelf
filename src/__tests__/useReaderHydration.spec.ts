import { describe, it, expect } from 'vite-plus/test'
import { ref, nextTick } from 'vue'
import { useReaderHydration, type OrderedGroup } from '@/composables/useReaderHydration'
import type { TargetBubble } from '@/composables/useReaderBubble'

describe('useReaderHydration - Permanent DOM Shell & Hysteresis Hydration Window', () => {
  function createGroups(count: number): OrderedGroup[] {
    return Array.from({ length: count }, (_, i) => ({
      pages: [i + 1],
      index: i,
    }))
  }

  it('hydrates all groups when total group count is within full hydration threshold', () => {
    const groups = ref(createGroups(30))
    const curIdx = ref(0)
    const comicKey = ref('local/test-comic')

    const hydration = useReaderHydration({
      orderedGroups: groups,
      currentGroupIndex: curIdx,
      comicKey,
    })

    // Total 30 <= threshold, all groups should be hydrated
    expect(hydration.isGroupHydrated(0)).toBe(true)
    expect(hydration.isGroupHydrated(15)).toBe(true)
    expect(hydration.isGroupHydrated(29)).toBe(true)
  })

  it('slices active window with forward and backward buffers in large comics (>45 groups)', () => {
    const groups = ref(createGroups(100))
    const curIdx = ref(50)
    const comicKey = ref('local/large-comic')

    const hydration = useReaderHydration({
      orderedGroups: groups,
      currentGroupIndex: curIdx,
      comicKey,
      bufferOverride: { forward: 15, backward: 30 },
    })

    // Current is 50, window is [50 - 30, 50 + 15] = [20, 65]
    expect(hydration.isGroupHydrated(50)).toBe(true) // current
    expect(hydration.isGroupHydrated(65)).toBe(true) // edge of forward
    expect(hydration.isGroupHydrated(20)).toBe(true) // edge of backward

    expect(hydration.isGroupHydrated(66)).toBe(false) // past forward buffer
    expect(hydration.isGroupHydrated(19)).toBe(false) // past backward buffer
    expect(hydration.isGroupHydrated(0)).toBe(false) // far behind
    expect(hydration.isGroupHydrated(99)).toBe(false) // far ahead
  })

  it('always hydrates group containing targetBubble regardless of distance', () => {
    const groups = ref(createGroups(100))
    const curIdx = ref(0)
    const comicKey = ref('local/large-comic')
    const targetBubble = ref<TargetBubble | null>({
      page: 90,
      box: [0.1, 0.2, 0.3, 0.4],
    })

    const hydration = useReaderHydration({
      orderedGroups: groups,
      currentGroupIndex: curIdx,
      comicKey,
      targetBubble,
      bufferOverride: { forward: 15, backward: 30 },
    })

    // Group 89 (page 90) is far outside normal window [0..15]
    expect(hydration.isGroupHydrated(0)).toBe(true)
    expect(hydration.isGroupHydrated(89)).toBe(true) // Target bubble privilege!

    // Intermediate distant groups remain unhydrated
    expect(hydration.isGroupHydrated(50)).toBe(false)
  })

  it('records physical page ratios and provides default ratio for unhydrated placeholders', async () => {
    const groups = ref(createGroups(50))
    const curIdx = ref(0)
    const comicKey = ref('local/test-ratio')

    const hydration = useReaderHydration({
      orderedGroups: groups,
      currentGroupIndex: curIdx,
      comicKey,
    })

    // Initially no ratio is recorded
    expect(hydration.getPageStyle(1)).toBeUndefined()

    // Page 1 decodes first with ratio '800 / 1200'
    hydration.onPageImageReady(1, '800 / 1200')
    expect(hydration.defaultComicRatio.value).toBe('800 / 1200')
    expect(hydration.getPageStyle(1)).toEqual({
      '--quiescent-ratio': '800 / 1200',
      aspectRatio: '800 / 1200',
    })

    // Unhydrated page 40 inherits defaultComicRatio
    expect(hydration.getPageStyle(40)).toEqual({
      '--quiescent-ratio': '800 / 1200',
      aspectRatio: '800 / 1200',
    })

    // Page 2 decodes with a specific ratio (e.g. double spread '1600 / 1200')
    hydration.onPageImageReady(2, '1600 / 1200')
    expect(hydration.getPageStyle(2)).toEqual({
      '--quiescent-ratio': '1600 / 1200',
      aspectRatio: '1600 / 1200',
    })

    // Switching comics resets recorded ratios
    comicKey.value = 'local/another-comic'
    await nextTick()
    expect(hydration.defaultComicRatio.value).toBeNull()
    expect(hydration.getPageStyle(1)).toBeUndefined()
  })
})

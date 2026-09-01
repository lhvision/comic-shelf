import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { defineComponent, ref, computed } from 'vue'
import { mount } from '@vue/test-utils'
import { useReaderData, type UseReaderDataReturn } from '@/composables/useReaderData'
import { DEFAULT_SETTINGS } from '@/composables/useReaderSettings'
import { api } from '@/api/client'
import type { ComicDetail } from '@/types'

const mockPush = vi.fn<(_url: string) => Promise<void>>()
const mockReplace = vi.fn<(_url: string) => Promise<void>>()
let mockRouteParams: Record<string, string> = { source: 'jm', sourceId: '123' }
let mockRouteQuery: Record<string, string | undefined> = { chapter: undefined }

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: mockRouteParams,
    query: mockRouteQuery,
  }),
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}))

describe('useReaderData', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockPush.mockReset()
    mockReplace.mockReset()
    mockRouteParams = { source: 'jm', sourceId: '123' }
    mockRouteQuery = { chapter: undefined }
  })

  it('loads detail on mount and initializes page/group positions', async () => {
    const mockDetail: ComicDetail = {
      meta: {
        source: 'jm',
        source_id: '123',
        display_id: '123',
        title: 'Sample Book',
        authors: ['Sample Author'],
        works: [],
        actors: [],
        tags: [],
        description: '',
        uploader: null,
        page_count: 10,
        published_at: '',
        updated_at: '',
        views: '',
        likes: '',
        comment_count: 0,
        favorite: false,
        cover_count: 4,
        source_url: '',
        pages: Array.from({ length: 10 }, (_, i) => ({
          index: i + 1,
          file: `${i + 1}.webp`,
          ext: 'webp',
          chapter: '',
          cached: true,
        })),
        imported_at: '',
        last_checked_at: '',
        raw: {},
      },
      cached_pages: 10,
      cache_complete: true,
      cover_paths: ['/cover-1.webp'],
    }

    vi.spyOn(api, 'detail').mockResolvedValueOnce(mockDetail)

    const scrollToGroupMock = vi.fn<(_idx: number, _beh?: ScrollBehavior) => void>()
    const preloadAroundMock = vi.fn<(_page: number) => void>()
    const scheduleChromeHideMock = vi.fn<() => void>()
    const resetAutoTurnCountdownMock = vi.fn<() => void>()

    let hookResult!: UseReaderDataReturn

    const TestComponent = defineComponent({
      setup() {
        const currentPage = ref(1)
        const currentGroupIndex = ref(0)
        const scopedPages = computed(() => [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

        hookResult = useReaderData({
          settings: { ...DEFAULT_SETTINGS },
          currentPage,
          currentGroupIndex,
          scopedPages,
          clampToScope: (p) => p,
          groupIndexForPage: (p) => Math.floor((p - 1) / 2),
          scrollToGroup: scrollToGroupMock,
          goToPage: vi.fn<(_page: number, _beh?: ScrollBehavior) => void>(),
          preloadAround: preloadAroundMock,
          showChromeTemporarily: vi.fn<() => void>(),
          scheduleChromeHide: scheduleChromeHideMock,
          resetAutoTurnCountdown: resetAutoTurnCountdownMock,
        })

        return () => null
      },
    })

    const wrapper = mount(TestComponent)
    // Wait for async onMounted promise
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(hookResult.loading.value).toBe(false)
    expect(hookResult.detail.value?.meta.title).toBe('Sample Book')
    expect(scrollToGroupMock).toHaveBeenCalledWith(0, 'instant')
    expect(scheduleChromeHideMock).toHaveBeenCalled()
    expect(preloadAroundMock).toHaveBeenCalledWith(1)
    expect(resetAutoTurnCountdownMock).toHaveBeenCalled()

    wrapper.unmount()
  })

  it('computes backTarget and executes backToDetail', () => {
    mockRouteParams = { source: 'jm', sourceId: '999' }
    mockRouteQuery = { chapter: 'ch-5' }

    let hookResult!: UseReaderDataReturn

    const TestComponent = defineComponent({
      setup() {
        hookResult = useReaderData({
          settings: { ...DEFAULT_SETTINGS },
          currentPage: ref(1),
          currentGroupIndex: ref(0),
          scopedPages: computed(() => [1]),
          clampToScope: (p) => p,
          groupIndexForPage: () => 0,
          scrollToGroup: vi.fn<(_idx: number, _beh?: ScrollBehavior) => void>(),
          goToPage: vi.fn<(_page: number, _beh?: ScrollBehavior) => void>(),
          preloadAround: vi.fn<(_page: number) => void>(),
          showChromeTemporarily: vi.fn<() => void>(),
          scheduleChromeHide: vi.fn<() => void>(),
          resetAutoTurnCountdown: vi.fn<() => void>(),
        })

        return () => null
      },
    })

    mount(TestComponent)

    expect(hookResult.backTarget.value).toBe('/comic/jm/999/chapter/ch-5')
    hookResult.backToDetail()
    expect(mockPush).toHaveBeenCalledWith('/comic/jm/999/chapter/ch-5')
  })
})

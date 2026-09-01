import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { defineComponent } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useReaderData, type UseReaderDataReturn } from '@/composables/useReaderData'
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

const mockToast = vi.fn<(_msg: string, _type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}))

describe('useReaderData', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockPush.mockReset()
    mockReplace.mockReset()
    mockToast.mockReset()
    mockRouteParams = { source: 'jm', sourceId: '123' }
    mockRouteQuery = { chapter: undefined }
  })

  it('loads detail on mount and triggers onLoaded callback', async () => {
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

    let loadingDuringOnLoaded: boolean | undefined
    const onLoadedMock = vi.fn<(_data: ComicDetail) => void>((_data) => {
      loadingDuringOnLoaded = hookResult.loading.value
    })
    let hookResult!: UseReaderDataReturn

    const TestComponent = defineComponent({
      setup() {
        hookResult = useReaderData({
          onLoaded: onLoadedMock,
        })
        return () => null
      },
    })

    const wrapper = mount(TestComponent)
    await flushPromises()

    expect(loadingDuringOnLoaded).toBe(false)
    expect(hookResult.loading.value).toBe(false)
    expect(hookResult.detail.value?.meta.title).toBe('Sample Book')
    expect(onLoadedMock).toHaveBeenCalledWith(mockDetail)

    wrapper.unmount()
  })

  it('handles API error with toast and redirects to comic detail view', async () => {
    vi.spyOn(api, 'detail').mockRejectedValueOnce(new Error('Network failure'))

    let hookResult!: UseReaderDataReturn
    const TestComponent = defineComponent({
      setup() {
        hookResult = useReaderData()
        return () => null
      },
    })

    const wrapper = mount(TestComponent)
    await flushPromises()

    expect(hookResult.loading.value).toBe(false)
    expect(mockToast).toHaveBeenCalledWith('Network failure', 'error')
    expect(mockReplace).toHaveBeenCalledWith('/comic/jm/123')

    wrapper.unmount()
  })

  it('computes backTarget and executes backToDetail', () => {
    mockRouteParams = { source: 'jm', sourceId: '999' }
    mockRouteQuery = { chapter: 'ch-5' }

    let hookResult!: UseReaderDataReturn

    const TestComponent = defineComponent({
      setup() {
        hookResult = useReaderData()
        return () => null
      },
    })

    mount(TestComponent)

    expect(hookResult.backTarget.value).toBe('/comic/jm/999/chapter/ch-5')
    hookResult.backToDetail()
    expect(mockPush).toHaveBeenCalledWith('/comic/jm/999/chapter/ch-5')
  })
})

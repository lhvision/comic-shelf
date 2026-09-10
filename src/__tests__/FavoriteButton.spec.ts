import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import FavoriteButton from '@/components/FavoriteButton.vue'

const mockSetFavorite =
  vi.fn<(source: string, sourceId: string, favorite: boolean) => Promise<{ ok: boolean }>>()
vi.mock('@/api/client', () => ({
  api: {
    setFavorite: (source: string, sourceId: string, favorite: boolean) =>
      mockSetFavorite(source, sourceId, favorite),
  },
}))

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}))

const mockRecordOfflineAction =
  vi.fn<(type: string, payload: Record<string, unknown>) => Promise<void>>()
vi.mock('@/composables/useOfflineSync', () => ({
  useOfflineSync: () => ({
    recordOfflineAction: mockRecordOfflineAction,
  }),
}))

describe('FavoriteButton component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSetFavorite.mockResolvedValue({ ok: true })
  })

  it('renders correct state and aria-pressed', () => {
    const wrapper = mount(FavoriteButton, {
      props: {
        source: 'jm',
        sourceId: '123456',
        favorite: false,
      },
    })

    const btn = wrapper.find('.favorite-button')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('aria-pressed')).toBe('false')
    expect(btn.attributes('aria-label')).toBe('标记喜欢')
  })

  it('emits toggled and calls api.setFavorite on click', async () => {
    const wrapper = mount(FavoriteButton, {
      props: {
        source: 'jm',
        sourceId: '123456',
        favorite: false,
      },
    })

    await wrapper.find('.favorite-button').trigger('click')

    expect(wrapper.emitted('toggled')).toBeTruthy()
    expect(wrapper.emitted('toggled')?.[0]).toEqual([true])
    expect(mockSetFavorite).toHaveBeenCalledWith('jm', '123456', true)
  })

  it('rolls back optimistic state and shows toast when api call fails', async () => {
    mockSetFavorite.mockRejectedValue(new Error('Network error'))

    const wrapper = mount(FavoriteButton, {
      props: {
        source: 'jm',
        sourceId: '123456',
        favorite: false,
      },
    })

    await wrapper.find('.favorite-button').trigger('click')

    const emitted = wrapper.emitted('toggled')
    expect(emitted).toHaveLength(2)
    // 第一次乐观触发
    expect(emitted?.[0]).toEqual([true])
    // 第二次回滚
    expect(emitted?.[1]).toEqual([false])
    expect(mockToast).toHaveBeenCalledWith('Network error', 'error')
  })

  it('records offline action and does not roll back when navigator is offline', async () => {
    mockSetFavorite.mockRejectedValue(new TypeError('Failed to fetch'))
    const originalOnLine = navigator.onLine
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })

    try {
      const wrapper = mount(FavoriteButton, {
        props: {
          source: 'jm',
          sourceId: '123456',
          favorite: false,
        },
      })

      await wrapper.find('.favorite-button').trigger('click')

      const emitted = wrapper.emitted('toggled')
      expect(emitted).toHaveLength(1)
      expect(emitted?.[0]).toEqual([true])
      expect(mockRecordOfflineAction).toHaveBeenCalledWith('favorite', {
        source: 'jm',
        sourceId: '123456',
        favorite: true,
      })
      expect(mockToast).toHaveBeenCalledWith('离线已记录，联网后自动同步', 'info')
    } finally {
      Object.defineProperty(navigator, 'onLine', { value: originalOnLine, configurable: true })
    }
  })

  it('does not render when interactive is false', () => {
    const wrapper = mount(FavoriteButton, {
      props: {
        source: 'jm',
        sourceId: '123456',
        favorite: true,
        interactive: false,
      },
    })

    expect(wrapper.find('.favorite-button').exists()).toBe(false)
  })
})

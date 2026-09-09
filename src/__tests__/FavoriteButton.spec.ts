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

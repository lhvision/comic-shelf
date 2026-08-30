import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderPassPopover from '@/components/ReaderPassPopover.vue'
import { useAuth } from '@/composables/useAuth'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    logout: vi.fn<() => Promise<{ ok: boolean }>>().mockResolvedValue({ ok: true }),
  },
  getStoredToken: vi.fn<() => string>(() => ''),
  setStoredToken: vi.fn<(token: string) => void>(),
  notifyAuthSuccess: vi.fn<() => void>(),
  onUnauthorized: vi.fn<(handler: () => void) => void>(),
}))

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}))

describe('ReaderPassPopover component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const { username } = useAuth()
    username.value = 'Alice'
  })

  it('renders trigger badge with book-open icon and reader name', () => {
    const wrapper = mount(ReaderPassPopover)
    const trigger = wrapper.find('.reader-badge-btn')
    expect(trigger.exists()).toBe(true)
    expect(trigger.find('.app-icon--book-open').exists()).toBe(true)
    expect(trigger.find('.reader-label').text()).toBe('〔 读者 · Alice 〕')
    expect(trigger.attributes('aria-haspopup')).toBe('dialog')
    expect(trigger.attributes('aria-expanded')).toBe('false')
  })

  it('renders fallback label when username is empty', () => {
    const { username } = useAuth()
    username.value = ''
    const wrapper = mount(ReaderPassPopover)
    const trigger = wrapper.find('.reader-badge-btn')
    expect(trigger.find('.reader-label').text()).toBe('〔 阅览室读者 〕')
  })

  it('renders popover panel with title, subtitle and status seal', () => {
    const wrapper = mount(ReaderPassPopover)
    expect(wrapper.find('.card-title').text()).toBe('借阅凭证')
    expect(wrapper.find('.card-subtitle').text()).toContain('READER PASS')
    expect(wrapper.find('.status-seal').text()).toBe('〔 持证阅览 〕')
    expect(wrapper.find('.plate-name').text()).toBe('Alice')
    expect(wrapper.find('.privilege-note').text()).toContain('专属书架已就绪')
  })

  it('handles two-step confirmation flow for returning pass', async () => {
    const wrapper = mount(ReaderPassPopover)
    const promptBtn = wrapper.find('.btn-return-pass')
    expect(promptBtn.exists()).toBe(true)
    expect(promptBtn.text()).toContain('交还借阅凭证')

    // Click to enter confirmation
    await promptBtn.trigger('click')
    expect(wrapper.find('.confirm-box').exists()).toBe(true)
    expect(wrapper.find('.confirm-title').text()).toBe('确定交还借阅凭证？')

    // Click cancel to abort
    const cancelBtn = wrapper.find('.confirm-actions .btn-secondary')
    expect(cancelBtn.exists()).toBe(true)
    expect(cancelBtn.text()).toBe('暂不交还')
    await cancelBtn.trigger('click')
    expect(wrapper.find('.confirm-box').exists()).toBe(false)
    expect(wrapper.find('.btn-return-pass').exists()).toBe(true)

    // Click again and confirm return
    await wrapper.find('.btn-return-pass').trigger('click')
    const confirmBtn = wrapper.find('.confirm-actions .btn-danger')
    expect(confirmBtn.exists()).toBe(true)
    expect(confirmBtn.text()).toBe('确认释放席位')

    await confirmBtn.trigger('click')
    expect(mockToast).toHaveBeenCalledWith('已交还借阅凭证，设备席位已释放', 'info')
  })

  it('handles logout failure gracefully and displays toast error', async () => {
    vi.mocked(api.logout).mockRejectedValueOnce(new Error('Network error'))
    const wrapper = mount(ReaderPassPopover)
    await wrapper.find('.btn-return-pass').trigger('click')
    await wrapper.find('.confirm-actions .btn-danger').trigger('click')
    expect(mockToast).toHaveBeenCalledWith('注销失败，请稍后重试', 'error')
  })
})

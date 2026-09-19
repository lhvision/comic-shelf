import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DirectPassModal from '@/components/detail/DirectPassModal.vue'
import { api } from '@/api/client'

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

const mockCopy = vi.fn<() => Promise<void>>()
vi.mock('@vueuse/core', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    useClipboard: () => ({
      copy: mockCopy,
      copied: { value: false },
    }),
  }
})

vi.mock('@/api/client', () => ({
  api: {
    createDirectPass: vi.fn<typeof api.createDirectPass>(),
  },
}))

describe('DirectPassModal Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCopy.mockResolvedValue(undefined)
  })

  function createWrapper(propsData = {}) {
    return mount(DirectPassModal, {
      props: {
        open: true,
        source: 'jm',
        sourceId: '123456',
        title: '测试漫画标题',
        pageCount: 120,
        lastRead: 45,
        ...propsData,
      },
      global: {
        stubs: {
          Teleport: true,
          AppIcon: {
            template: '<span class="app-icon" :data-name="name" />',
            props: ['name'],
          },
        },
      },
    })
  }

  it('renders comic title and page count in header', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('《测试漫画标题》')
    expect(wrapper.text()).toContain('全书共 120 页')
    expect(wrapper.text()).toContain('有效借阅时长 (到期自动作废)')
  })

  it('initializes start page from lastRead when provided', () => {
    const wrapper = createWrapper({ lastRead: 45 })
    const input = wrapper.find<HTMLInputElement>('#direct-pass-page')
    expect(input.element.value).toBe('45')
  })

  it('switches start page with quick buttons', async () => {
    const wrapper = createWrapper({ lastRead: 45 })
    const buttons = wrapper.findAll('.quick-page-buttons button')
    const firstPageBtn = buttons[0]
    expect(firstPageBtn).toBeDefined()
    expect(firstPageBtn!.text()).toContain('第 1 页')

    await firstPageBtn!.trigger('click')
    const input = wrapper.find<HTMLInputElement>('#direct-pass-page')
    expect(input.element.value).toBe('1')

    const lastReadBtn = buttons[1]
    expect(lastReadBtn).toBeDefined()
    expect(lastReadBtn!.text()).toContain('上次进度')
    await lastReadBtn!.trigger('click')
    expect(input.element.value).toBe('45')
  })

  it('selects different duration card with click and keyboard', async () => {
    const wrapper = createWrapper()
    const cards = wrapper.findAll('.duration-card')
    expect(cards.length).toBe(4)

    // Second card (24 hours) is active by default (recommended)
    expect(cards[1]!.classes()).toContain('is-active')
    expect(cards[1]!.attributes('aria-checked')).toBe('true')

    // Click 2 hours card (index 0)
    await cards[0]!.trigger('click')
    expect(cards[0]!.classes()).toContain('is-active')
    expect(cards[0]!.attributes('aria-checked')).toBe('true')
    expect(cards[1]!.classes()).not.toContain('is-active')

    // Test keyboard ArrowRight navigation
    await cards[0]!.trigger('keydown', { key: 'ArrowRight' })
    expect(cards[1]!.classes()).toContain('is-active')
  })

  it('calls api.createDirectPass and displays bookplate result', async () => {
    vi.mocked(api.createDirectPass).mockResolvedValueOnce({
      token: 'mock-direct-token-1234567890',
      direct_url: '/read/jm/123456/1?temp_token=mock-direct-token-1234567890',
      source: 'jm',
      source_id: '123456',
      page_index: 45,
      expires_at: 1800000000,
      expires_in: 86400,
    })

    const wrapper = createWrapper({ lastRead: 45 })
    const generateBtn = wrapper
      .findAll('.modal-footer-actions button')
      .find((b) => b.text().includes('立即签发'))
    expect(generateBtn).toBeDefined()

    await generateBtn!.trigger('click')

    expect(api.createDirectPass).toHaveBeenCalledWith({
      source: 'jm',
      source_id: '123456',
      page_index: 45,
      ttl_seconds: 86400,
    })

    expect(mockToast).toHaveBeenCalledWith('已成功签发单本沙箱直达链接', 'success')
    expect(wrapper.text()).toContain('纸间 · 借阅笺已立')
    const linkInput = wrapper.find<HTMLInputElement>('.link-input')
    expect(linkInput.element.value).toContain(
      '/read/jm/123456/1?temp_token=mock-direct-token-1234567890',
    )

    // Allows re-configuration
    const reconfigBtn = wrapper
      .findAll('.modal-footer-actions button')
      .find((b) => b.text().includes('重新配置'))
    expect(reconfigBtn).toBeDefined()
    await reconfigBtn!.trigger('click')
    expect(wrapper.text()).toContain('有效借阅时长 (到期自动作废)')
  })

  it('supports Enter key to generate pass directly from input', async () => {
    vi.mocked(api.createDirectPass).mockResolvedValueOnce({
      token: 'mock-direct-token-1234567890',
      direct_url: '/read/jm/123456/1?temp_token=mock-direct-token-1234567890',
      source: 'jm',
      source_id: '123456',
      page_index: 10,
      expires_at: 1800000000,
      expires_in: 86400,
    })

    const wrapper = createWrapper({ lastRead: 10 })
    const input = wrapper.find<HTMLInputElement>('#direct-pass-page')
    await input.trigger('keydown.enter')

    expect(api.createDirectPass).toHaveBeenCalledWith({
      source: 'jm',
      source_id: '123456',
      page_index: 10,
      ttl_seconds: 86400,
    })
  })

  it('handles copy button click', async () => {
    vi.mocked(api.createDirectPass).mockResolvedValueOnce({
      token: 'mock-direct-token-1234567890',
      direct_url: '/read/jm/123456/1?temp_token=mock-direct-token-1234567890',
      source: 'jm',
      source_id: '123456',
      page_index: 1,
      expires_at: 1800000000,
      expires_in: 7200,
    })

    const wrapper = createWrapper()
    const generateBtn = wrapper
      .findAll('.modal-footer-actions button')
      .find((b) => b.text().includes('立即签发'))
    await generateBtn!.trigger('click')

    const copyBtn = wrapper.find('.btn-copy')
    expect(copyBtn.exists()).toBe(true)
    await copyBtn.trigger('click')

    expect(mockCopy).toHaveBeenCalled()
    expect(mockToast).toHaveBeenCalledWith('已复制直达阅读链接到剪贴板', 'success')
  })

  it('closes modal when clicking cancel button', async () => {
    const wrapper = createWrapper()
    const cancelBtn = wrapper
      .findAll('.modal-footer-actions button')
      .find((b) => b.text().includes('取消'))
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger('click')

    expect(wrapper.emitted('update:open')?.[0]).toEqual([false])
  })
})

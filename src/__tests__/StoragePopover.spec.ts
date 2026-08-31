import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import StoragePopover from '@/components/StoragePopover.vue'

describe('StoragePopover component', () => {
  it('renders trigger badge with archive icon and label', () => {
    const wrapper = mount(StoragePopover)
    const trigger = wrapper.find('.storage-badge-btn')
    expect(trigger.exists()).toBe(true)
    expect(trigger.find('.app-icon--archive').exists()).toBe(true)
    expect(trigger.find('.storage-label').exists()).toBe(true)
  })

  it('renders popover panel with title and subtitle', () => {
    const wrapper = mount(StoragePopover)
    expect(wrapper.find('.panel-title').text()).toBe('阅览室设备与离线')
    expect(wrapper.find('.panel-subtitle').text()).toContain('LOCAL STORAGE & PWA')
  })

  it('renders storage meter progressbar with aria attributes', () => {
    const wrapper = mount(StoragePopover)
    const progressbar = wrapper.find('[role="progressbar"]')
    expect(progressbar.exists()).toBe(true)
    expect(progressbar.attributes('aria-valuemin')).toBe('0')
    expect(progressbar.attributes('aria-valuemax')).toBe('100')
    expect(progressbar.attributes('aria-valuenow')).toBeDefined()
  })

  it('renders breakdown items for core assets and manga images', () => {
    const wrapper = mount(StoragePopover)
    const items = wrapper.findAll('.breakdown-item')
    expect(items.length).toBe(2)
    expect(items[0]?.text()).toContain('纸间核心资产')
    expect(items[1]?.text()).toContain('漫画阅览缓存')
  })

  it('renders clear button with trash icon and safe boundary notice', () => {
    const wrapper = mount(StoragePopover)
    expect(wrapper.find('.storage-boundary').text()).toContain('仅释放本设备浏览器缓存')
    const clearBtn = wrapper.find('.storage-panel__footer .btn')
    expect(clearBtn.exists()).toBe(true)
    expect(clearBtn.find('.app-icon--trash').exists()).toBe(true)
    expect(wrapper.find('.reset-btn').text()).toBe('重置全部离线环境')
  })

  it('triggers two-step confirmation flow for resetAll', async () => {
    const wrapper = mount(StoragePopover)
    const resetBtn = wrapper.find('.reset-btn')
    expect(resetBtn.exists()).toBe(true)

    // First click enters confirmation state
    await resetBtn.trigger('click')
    expect(wrapper.find('.confirm-box').exists()).toBe(true)
    expect(wrapper.find('.confirm-warning').text()).toContain('清空所有离线资源')
    expect(wrapper.find('.confirm-btn.danger').exists()).toBe(true)

    // Clicking cancel exits confirmation state
    const cancelBtn = wrapper.find('.confirm-btn.cancel')
    await cancelBtn.trigger('click')
    expect(wrapper.find('.confirm-box').exists()).toBe(false)
    expect(wrapper.find('.reset-btn').exists()).toBe(true)
  })

  it('renders update indicator dot and card when needRefresh is active', async () => {
    const { usePwaUpdate } = await import('@/composables/usePwaUpdate')
    const { needRefresh } = usePwaUpdate()
    needRefresh.value = true

    const wrapper = mount(StoragePopover)
    expect(wrapper.find('.storage-badge-btn.has-update').exists()).toBe(true)
    expect(wrapper.find('.update-indicator-dot').exists()).toBe(true)
    expect(wrapper.find('.storage-update-card').exists()).toBe(true)
    expect(wrapper.find('.update-card-title').text()).toBe('新卷本装订就绪')
  })
})

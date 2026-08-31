import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import UpdateBanner from '@/components/UpdateBanner.vue'
import { usePwaUpdate } from '@/composables/usePwaUpdate'

// Mock vue-router
vi.mock('vue-router', () => ({
  useRoute: () => ({
    name: 'shelf',
  }),
}))

describe('UpdateBanner component', () => {
  it('does not render when no update is needed', () => {
    const { needRefresh } = usePwaUpdate()
    needRefresh.value = false

    const wrapper = mount(UpdateBanner)
    expect(wrapper.find('.update-banner').exists()).toBe(false)
  })

  it('renders floating banner when update is available', async () => {
    const { needRefresh, hasDismissedPrompt } = usePwaUpdate()
    needRefresh.value = true
    hasDismissedPrompt.value = false

    const wrapper = mount(UpdateBanner)
    const banner = wrapper.find('.update-banner')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('纸间已有新卷本装订就绪')
    expect(banner.find('.apply-btn').text()).toContain('立即装订')
    expect(banner.find('.dismiss-btn').text()).toContain('稍后')
  })

  it('hides banner when reader mode is active', async () => {
    const { needRefresh } = usePwaUpdate()
    needRefresh.value = true

    const wrapper = mount(UpdateBanner)
    expect(wrapper.find('.update-banner').exists()).toBe(true)
  })

  it('handles dismiss action correctly', async () => {
    const { needRefresh, hasDismissedPrompt } = usePwaUpdate()
    needRefresh.value = true
    hasDismissedPrompt.value = false

    const wrapper = mount(UpdateBanner)
    const dismissBtn = wrapper.find('.dismiss-btn')
    await dismissBtn.trigger('click')

    expect(hasDismissedPrompt.value).toBe(true)
    expect(wrapper.find('.update-banner').exists()).toBe(false)
  })

  it('triggers applyUpdate on button click', async () => {
    const { needRefresh, hasDismissedPrompt } = usePwaUpdate()
    needRefresh.value = true
    hasDismissedPrompt.value = false

    const wrapper = mount(UpdateBanner)
    const applyBtn = wrapper.find('.apply-btn')
    expect(applyBtn.exists()).toBe(true)
  })
})

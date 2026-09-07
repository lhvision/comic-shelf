import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ImportPanel from '@/components/ImportPanel.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn<(to: string) => void>(),
  }),
}))

vi.mock('@/api/client', () => ({
  api: {
    importLocalPath: vi.fn<
      () => Promise<{
        meta: { source: string; source_id: string; title: string; page_count: number }
      }>
    >(),
    getSettings: vi
      .fn<() => Promise<{ concurrency: number; guest_hide_new_comics: boolean }>>()
      .mockResolvedValue({ concurrency: 4, guest_hide_new_comics: false }),
    getLibrary: vi.fn<() => Promise<unknown[]>>().mockResolvedValue([]),
    getSources: vi.fn<() => Promise<unknown[]>>().mockResolvedValue([]),
  },
  onAuthSuccess: vi.fn<() => void>(),
  onUnauthorized: vi.fn<() => void>(),
}))

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}))

describe('ImportPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('renders JM tab by default with remote download settings', () => {
    const pinia = createPinia()
    const wrapper = mount(ImportPanel, {
      global: {
        plugins: [pinia],
      },
    })

    // Tabs
    const tabs = wrapper.findAll('.panel-tab')
    expect(tabs[0]?.text()).toBe('禁漫车号')
    expect(tabs[0]?.classes()).toContain('is-active')
    expect(tabs[1]?.text()).toBe('哔咔漫画')
    expect(tabs[2]?.text()).toBe('本地自建 / 拆帧')

    // JM input form
    expect(wrapper.find('.field-prefix').text()).toBe('JM')

    // In JM tab, both "同时缓存全部页面" and "下载并发" are visible
    expect(wrapper.text()).toContain('同时缓存全部页面')
    expect(wrapper.text()).toContain('下载并发')
    expect(wrapper.text()).toContain('新入库默认对访客隐藏')
  })

  it('renders PicAcg tab when clicking 哔咔漫画', async () => {
    const pinia = createPinia()
    const wrapper = mount(ImportPanel, {
      global: {
        plugins: [pinia],
      },
    })

    const tabs = wrapper.findAll('.panel-tab')
    // Click "哔咔漫画" tab
    await tabs[1]?.trigger('click')
    expect(tabs[1]?.classes()).toContain('is-active')

    // PicAcg input form
    expect(wrapper.find('.field-prefix').text()).toBe('PICA')
    expect(wrapper.text()).toContain('同时缓存全部页面')
    expect(wrapper.text()).toContain('下载并发')
  })

  it('hides "同时缓存全部页面" and "下载并发" when switching to local tab', async () => {
    const pinia = createPinia()
    const wrapper = mount(ImportPanel, {
      global: {
        plugins: [pinia],
      },
    })

    const tabs = wrapper.findAll('.panel-tab')
    // Click "本地自建 / 拆帧" tab
    await tabs[2]?.trigger('click')
    expect(tabs[2]?.classes()).toContain('is-active')

    // Local input form
    expect(wrapper.find('.field-prefix').text()).toBe('PATH')
    expect(wrapper.text()).toContain('进入自建图集工坊')

    // In Local tab, remote download settings should be hidden
    expect(wrapper.text()).not.toContain('同时缓存全部页面')
    expect(wrapper.text()).not.toContain('下载并发')

    // But library-wide preference "新入库默认对访客隐藏" remains
    expect(wrapper.text()).toContain('新入库默认对访客隐藏')
  })

  it('hides internal panel-tabs and locks to picacg when source="picacg" prop is provided', () => {
    const pinia = createPinia()
    const wrapper = mount(ImportPanel, {
      props: {
        source: 'picacg',
      },
      global: {
        plugins: [pinia],
      },
    })

    // Panel tabs should NOT be rendered when source prop is provided (decoupled architecture)
    expect(wrapper.findAll('.panel-tab').length).toBe(0)

    // Displays PicAcg dedicated heading and input
    expect(wrapper.text()).toContain('收录哔咔画卷')
    expect(wrapper.find('.field-prefix').text()).toBe('PICA')
    expect(wrapper.text()).toContain('同时缓存全部页面')
  })

  it('hides internal panel-tabs and locks to local when source="local" prop is provided', () => {
    const pinia = createPinia()
    const wrapper = mount(ImportPanel, {
      props: {
        source: 'local',
      },
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.findAll('.panel-tab').length).toBe(0)
    expect(wrapper.text()).toContain('收录本地图集')
    expect(wrapper.find('.field-prefix').text()).toBe('PATH')
  })

  it('toggles is-mobile-collapsed class when mobile collapse bar is clicked', async () => {
    const pinia = createPinia()
    const wrapper = mount(ImportPanel, {
      global: {
        plugins: [pinia],
      },
    })

    // Initially collapsed on mobile by default
    expect(wrapper.classes()).toContain('is-mobile-collapsed')

    const bar = wrapper.find('.mobile-collapse-bar')
    await bar.trigger('click')

    // Expanded
    expect(wrapper.classes()).not.toContain('is-mobile-collapsed')

    // Click again to collapse
    await bar.trigger('click')
    expect(wrapper.classes()).toContain('is-mobile-collapsed')
  })
})

import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DetailActionBar from '@/components/detail/DetailActionBar.vue'

describe('DetailActionBar', () => {
  const defaultProps = {
    title: '测试漫画',
    lastRead: 1,
    cachePercent: 50,
    caching: false,
    refreshing: false,
    cacheComplete: false,
    cachedPages: 10,
    pageCount: 20,
    canWrite: true,
    source: 'jm',
    customPages: false,
  }

  it('renders "刷新资料" button when refreshing is false', () => {
    const wrapper = mount(DetailActionBar, {
      props: defaultProps,
    })

    const buttons = wrapper.findAll('button')
    const refreshBtn = buttons.find((btn) =>
      btn.attributes('title')?.includes('同步作品章节与最新元数据'),
    )
    expect(refreshBtn).toBeDefined()
    expect(refreshBtn?.text()).toContain('刷新资料')
    expect(refreshBtn?.classes()).not.toContain('is-loading')
    expect(refreshBtn?.attributes('disabled')).toBeUndefined()
  })

  it('renders spinner and disabled state when refreshing is true', () => {
    const wrapper = mount(DetailActionBar, {
      props: {
        ...defaultProps,
        refreshing: true,
      },
    })

    const buttons = wrapper.findAll('button')
    const refreshBtn = buttons.find((btn) =>
      btn.attributes('title')?.includes('同步作品章节与最新元数据'),
    )
    expect(refreshBtn).toBeDefined()
    expect(refreshBtn?.classes()).toContain('is-loading')
    expect(refreshBtn?.find('.btn-spinner').exists()).toBe(true)
    expect(refreshBtn?.attributes('disabled')).toBeDefined()
    expect(refreshBtn?.attributes('aria-busy')).toBe('true')
  })

  it('disables "刷新资料" when caching is in progress', () => {
    const wrapper = mount(DetailActionBar, {
      props: {
        ...defaultProps,
        caching: true,
      },
    })

    const buttons = wrapper.findAll('button')
    const refreshBtn = buttons.find((btn) =>
      btn.attributes('title')?.includes('同步作品章节与最新元数据'),
    )
    expect(refreshBtn).toBeDefined()
    expect(refreshBtn?.attributes('disabled')).toBeDefined()
  })

  it('disables "缓存全部" when refreshing is in progress', () => {
    const wrapper = mount(DetailActionBar, {
      props: {
        ...defaultProps,
        refreshing: true,
      },
    })

    const buttons = wrapper.findAll('button')
    const cacheBtn = buttons.find((btn) => btn.text().includes('缓存全部'))
    expect(cacheBtn).toBeDefined()
    expect(cacheBtn?.attributes('disabled')).toBeDefined()
  })

  it('emits refreshMetadata when clicked while enabled', async () => {
    const wrapper = mount(DetailActionBar, {
      props: defaultProps,
    })

    const buttons = wrapper.findAll('button')
    const refreshBtn = buttons.find((btn) =>
      btn.attributes('title')?.includes('同步作品章节与最新元数据'),
    )
    expect(refreshBtn).toBeDefined()
    await refreshBtn?.trigger('click')
    expect(wrapper.emitted('refreshMetadata')).toHaveLength(1)
  })
})

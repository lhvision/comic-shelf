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

  it('renders "刷新资料" menu item inside 更多 menu when refreshing is false', () => {
    const wrapper = mount(DetailActionBar, {
      props: defaultProps,
    })

    const items = wrapper.findAll('[role="menuitem"]')
    const refreshItem = items.find((item) => item.text().includes('刷新资料'))
    expect(refreshItem).toBeDefined()
    expect(refreshItem?.attributes('disabled')).toBeUndefined()
  })

  it('disables "刷新资料" and shows refreshing label when refreshing is true', () => {
    const wrapper = mount(DetailActionBar, {
      props: {
        ...defaultProps,
        refreshing: true,
      },
    })

    const items = wrapper.findAll('[role="menuitem"]')
    const refreshItem = items.find((item) => item.text().includes('刷新中…'))
    expect(refreshItem).toBeDefined()
    expect(refreshItem?.attributes('disabled')).toBeDefined()
  })

  it('disables "刷新资料" when caching is in progress', () => {
    const wrapper = mount(DetailActionBar, {
      props: {
        ...defaultProps,
        caching: true,
      },
    })

    const items = wrapper.findAll('[role="menuitem"]')
    const refreshItem = items.find((item) => item.text().includes('刷新资料'))
    expect(refreshItem).toBeDefined()
    expect(refreshItem?.attributes('disabled')).toBeDefined()
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

  it('emits refreshMetadata when clicking "刷新资料" in 更多 menu', async () => {
    const wrapper = mount(DetailActionBar, {
      props: defaultProps,
    })

    const items = wrapper.findAll('[role="menuitem"]')
    const refreshItem = items.find((item) => item.text().includes('刷新资料'))
    expect(refreshItem).toBeDefined()
    await refreshItem?.trigger('click')
    expect(wrapper.emitted('refreshMetadata')).toHaveLength(1)
  })

  describe('从第 1 页开始 (Restart reading confirmation)', () => {
    it('directly emits startReading(1) when lastRead <= 1', async () => {
      const wrapper = mount(DetailActionBar, {
        props: {
          ...defaultProps,
          lastRead: 1,
        },
      })

      const restartBtn = wrapper.findAll('button').find((btn) => btn.text() === '从第 1 页开始')
      expect(restartBtn).toBeDefined()
      await restartBtn?.trigger('click')

      expect(wrapper.emitted('startReading')).toEqual([[1]])
      expect(wrapper.text()).not.toContain('从第 1 页重新开始？')
    })

    it('directly emits startReading(1) when comic is completed (lastRead >= pageCount)', async () => {
      const wrapper = mount(DetailActionBar, {
        props: {
          ...defaultProps,
          lastRead: 20,
          pageCount: 20,
        },
      })

      const restartBtn = wrapper.findAll('button').find((btn) => btn.text() === '从第 1 页开始')
      expect(restartBtn).toBeDefined()
      await restartBtn?.trigger('click')

      expect(wrapper.emitted('startReading')).toEqual([[1]])
      expect(wrapper.text()).not.toContain('从第 1 页重新开始？')
    })

    it('opens confirmation modal when in-progress (1 < lastRead < pageCount)', async () => {
      const wrapper = mount(DetailActionBar, {
        props: {
          ...defaultProps,
          lastRead: 8,
          pageCount: 20,
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      const restartBtn = wrapper.findAll('button').find((btn) => btn.text() === '从第 1 页开始')
      await restartBtn?.trigger('click')

      // Should NOT emit startReading yet
      expect(wrapper.emitted('startReading')).toBeUndefined()

      // Modal should be open
      expect(wrapper.text()).toContain('从第 1 页重新开始？')
      expect(wrapper.text()).toContain('当前已读至第 8 页（共 20 页）')
      expect(wrapper.text()).toContain('从头开始阅读将更新你的阅读断点')

      // Clicking cancel closes modal without emitting
      const cancelBtn = wrapper
        .findAll('button')
        .find((btn) => btn.text() === '取消' && btn.element.closest('dialog'))
      await cancelBtn?.trigger('click')
      expect(wrapper.emitted('startReading')).toBeUndefined()
    })

    it('confirms restart and emits startReading(1) when clicking confirm', async () => {
      const wrapper = mount(DetailActionBar, {
        props: {
          ...defaultProps,
          lastRead: 8,
          pageCount: 20,
          lastReadLabel: '第 2 话 · 第 3 页',
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      const restartBtn = wrapper.findAll('button').find((btn) => btn.text() === '从第 1 页开始')
      await restartBtn?.trigger('click')

      expect(wrapper.text()).toContain('第 2 话 · 第 3 页（全书第 8 页 / 共 20 页）')

      const confirmBtn = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('确认从头阅读'))
      expect(confirmBtn).toBeDefined()
      await confirmBtn?.trigger('click')

      expect(wrapper.emitted('startReading')).toEqual([[1]])
    })
  })
})

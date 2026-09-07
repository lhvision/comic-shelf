import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import PageTile from '@/components/detail/PageTile.vue'

describe('PageTile', () => {
  it('renders page number and uncached status by default', () => {
    const wrapper = mount(PageTile, {
      props: {
        source: 'picacg',
        sourceId: '5ebe89bf63918511c2c362a7',
        index: 52,
        cached: false,
        label: 2,
      },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    expect(wrapper.find('.page-index').text()).toBe('002')
    expect(wrapper.find('.page-state').text()).toBe('待缓存')
    expect(wrapper.attributes('data-cached')).toBe('false')
  })

  it('emits cached event with index when image finishes loading and page is not cached', async () => {
    const wrapper = mount(PageTile, {
      props: {
        source: 'picacg',
        sourceId: '5ebe89bf63918511c2c362a7',
        index: 52,
        cached: false,
        label: 2,
      },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)

    await img.trigger('load')
    expect(wrapper.emitted('cached')).toEqual([[52]])
  })

  it('does not emit cached event on image load if already marked cached', async () => {
    const wrapper = mount(PageTile, {
      props: {
        source: 'picacg',
        sourceId: '5ebe89bf63918511c2c362a7',
        index: 51,
        cached: true,
        label: 1,
      },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    expect(wrapper.find('.page-state').text()).toBe('本地')
    expect(wrapper.attributes('data-cached')).toBe('true')

    const img = wrapper.find('img')
    await img.trigger('load')
    expect(wrapper.emitted('cached')).toBeUndefined()
  })
})

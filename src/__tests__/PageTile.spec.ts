import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { defineComponent, vaporInteropPlugin } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import PageTile from '@/components/detail/PageTile.vue'

describe('PageTile (Vapor Mode)', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/comic/:source/:sourceId/read/:page?', component: { template: '<div />' } },
    ],
  })

  const mountOptions = {
    global: {
      plugins: [vaporInteropPlugin, router],
    },
  }

  interface PageTileProps {
    source: string
    sourceId: string
    index: number
    cached: boolean
    label?: number
    chapterId?: string
  }

  function createHost(props: PageTileProps) {
    return mount(
      defineComponent({
        components: { PageTile },
        setup() {
          return { props }
        },
        template: '<div><PageTile v-bind="props" @cached="$emit(\'cached\', $event)" /></div>',
      }),
      mountOptions,
    )
  }

  it('renders page number and uncached status by default', () => {
    const wrapper = createHost({
      source: 'picacg',
      sourceId: '5ebe89bf63918511c2c362a7',
      index: 52,
      cached: false,
      label: 2,
    })

    expect(wrapper.find('.page-index').text()).toBe('002')
    expect(wrapper.find('.page-state').text()).toBe('待缓存')
    expect(wrapper.find('.page-tile').attributes('data-cached')).toBe('false')
    expect(wrapper.find('a.page-tile').attributes('href')).toBe(
      '/comic/picacg/5ebe89bf63918511c2c362a7/read/52',
    )
  })

  it('emits cached event with index when image finishes loading and page is not cached', async () => {
    const wrapper = createHost({
      source: 'picacg',
      sourceId: '5ebe89bf63918511c2c362a7',
      index: 52,
      cached: false,
      label: 2,
    })

    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)

    await img.trigger('load')
    expect(wrapper.emitted('cached')).toEqual([[52]])
  })

  it('does not emit cached event on image load if already marked cached', async () => {
    const wrapper = createHost({
      source: 'picacg',
      sourceId: '5ebe89bf63918511c2c362a7',
      index: 51,
      cached: true,
      label: 1,
    })

    expect(wrapper.find('.page-state').text()).toBe('本地')
    expect(wrapper.find('.page-tile').attributes('data-cached')).toBe('true')

    const img = wrapper.find('img')
    await img.trigger('load')
    expect(wrapper.emitted('cached')).toBeUndefined()
  })
})

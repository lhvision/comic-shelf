import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderLoadingState from '@/components/reader/ReaderLoadingState.vue'

describe('ReaderLoadingState.vue', () => {
  it('renders default variant 1 and default text', () => {
    const wrapper = mount(ReaderLoadingState)
    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/loading-1.webp')
    expect(wrapper.text()).toContain('正在装订书页…')
    expect(wrapper.attributes('role')).toBe('status')
  })

  it('renders variant 3 with custom text', () => {
    const wrapper = mount(ReaderLoadingState, {
      props: {
        variant: 3,
        text: '正在整理书页…',
      },
    })
    const img = wrapper.find('img')
    expect(img.attributes('src')).toBe('/loading-3.webp')
    expect(wrapper.text()).toContain('正在整理书页…')
  })

  it('applies is-compact class when compact is true', () => {
    const wrapper = mount(ReaderLoadingState, {
      props: {
        compact: true,
      },
    })
    expect(wrapper.classes()).toContain('is-compact')
  })
})

import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AmbientWatermark from '@/components/AmbientWatermark.vue'

describe('AmbientWatermark.vue', () => {
  it('renders with default props and css v-bind', () => {
    const wrapper = mount(AmbientWatermark)
    expect(wrapper.classes()).toContain('ambient-watermark')
    expect(wrapper.classes()).toContain('is-page')
    expect(wrapper.attributes('aria-hidden')).toBe('true')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('renders modal variant with custom src via css v-bind', () => {
    const wrapper = mount(AmbientWatermark, {
      props: {
        variant: 'modal',
        src: '/loading-2.webp',
      },
    })
    expect(wrapper.classes()).toContain('is-modal')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.html()).toContain('ambient-watermark')
  })
})

import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AppIcon from '@/components/AppIcon.vue'
import { BaseIcon, IconClose, IconHeartFilled } from '@/components/icons'

describe('AppIcon & Icon components', () => {
  it('renders close icon with default md size and aria-hidden via AppIcon', () => {
    const wrapper = mount(AppIcon, {
      props: {
        name: 'close',
      },
    })

    expect(wrapper.classes()).toContain('app-icon')
    expect(wrapper.classes()).toContain('app-icon--close')
    expect(wrapper.attributes('width')).toBe('16px')
    expect(wrapper.attributes('height')).toBe('16px')
    expect(wrapper.attributes('aria-hidden')).toBe('true')
  })

  it('renders direct IconClose component directly without dispatcher', () => {
    const wrapper = mount(IconClose, {
      props: {
        size: 'sm',
      },
    })

    expect(wrapper.classes()).toContain('app-icon')
    expect(wrapper.classes()).toContain('app-icon--close')
    expect(wrapper.attributes('width')).toBe('14px')
    expect(wrapper.attributes('height')).toBe('14px')
  })

  it('renders direct IconHeartFilled with currentColor fill', () => {
    const wrapper = mount(IconHeartFilled, {
      props: {
        size: 'lg',
      },
    })

    expect(wrapper.classes()).toContain('app-icon--heart-filled')
    expect(wrapper.attributes('width')).toBe('20px')
    const path = wrapper.find('path')
    expect(path.attributes('fill')).toBe('currentColor')
  })

  it('renders BaseIcon with custom slot and size', () => {
    const wrapper = mount(BaseIcon, {
      props: {
        size: 'xl',
      },
      slots: {
        default: '<circle cx="12" cy="12" r="10" />',
      },
    })

    expect(wrapper.classes()).toContain('app-icon')
    expect(wrapper.attributes('width')).toBe('24px')
    expect(wrapper.attributes('height')).toBe('24px')
    expect(wrapper.find('circle').exists()).toBe(true)
  })
})

import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderHoverPreview from '@/components/reader/ReaderHoverPreview.vue'

describe('ReaderHoverPreview - Hover Preview Popover', () => {
  const defaultProps = {
    show: true,
    page: 5,
    source: 'local',
    sourceId: 'demo-comic',
    anchorX: 120,
    ratio: '800 / 1200',
    toLocalPage: (p: number) => p,
    groupTip: '第 3 屏 · [5-6]',
  }

  it('renders popover with correct page label and group tip when show is true', () => {
    const wrapper = mount(ReaderHoverPreview, {
      props: defaultProps,
    })

    expect(wrapper.find('.reader-hover-preview').exists()).toBe(true)
    expect(wrapper.find('.preview-page-num').text()).toContain('第 5 页')
    expect(wrapper.find('.preview-group-tip').text()).toBe('第 3 屏 · [5-6]')
  })

  it('does not render when show is false', () => {
    const wrapper = mount(ReaderHoverPreview, {
      props: {
        ...defaultProps,
        show: false,
      },
    })

    expect(wrapper.find('.reader-hover-preview').exists()).toBe(false)
  })

  it('sets position and aspect ratio styles properly', () => {
    const wrapper = mount(ReaderHoverPreview, {
      props: defaultProps,
    })

    const aside = wrapper.find('.reader-hover-preview')
    expect(aside.attributes('style')).toContain('left: 120px')
    expect(aside.attributes('style')).toContain('--hover-ratio: 800 / 1200')
  })
})

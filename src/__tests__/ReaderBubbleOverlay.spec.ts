import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderBubbleOverlay from '@/components/ReaderBubbleOverlay.vue'

describe('ReaderBubbleOverlay component', () => {
  it('does not render when targetBubble is null or undefined', () => {
    const wrapper = mount(ReaderBubbleOverlay, {
      props: {
        pageIndex: 1,
        targetBubble: null,
      },
    })
    expect(wrapper.find('.reader-bubble-box').exists()).toBe(false)
  })

  it('does not render when pageIndex does not match targetBubble.page', () => {
    const wrapper = mount(ReaderBubbleOverlay, {
      props: {
        pageIndex: 2,
        targetBubble: {
          page: 1,
          box: [0.1, 0.2, 0.4, 0.6],
        },
      },
    })
    expect(wrapper.find('.reader-bubble-box').exists()).toBe(false)
  })

  it('waits and does not render while imageReady is false', () => {
    const wrapper = mount(ReaderBubbleOverlay, {
      props: {
        pageIndex: 1,
        targetBubble: {
          page: 1,
          box: [0.1, 0.2, 0.4, 0.6],
        },
        imageReady: false,
      },
    })
    expect(wrapper.find('.reader-bubble-box').exists()).toBe(false)
  })

  it('renders highlight box positioned via CSS percentage when page matches', () => {
    const wrapper = mount(ReaderBubbleOverlay, {
      props: {
        pageIndex: 42,
        targetBubble: {
          page: 42,
          box: [0.1, 0.2, 0.4, 0.7],
        },
      },
    })

    const box = wrapper.find('.reader-bubble-box')
    expect(box.exists()).toBe(true)

    const style = box.attributes('style')
    expect(style).toContain('top: 10%')
    expect(style).toContain('left: 20%')
    expect(style).toContain('height: 30%')
    expect(style).toContain('width: 50%')

    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.attributes('aria-live')).toBe('polite')
  })

  it('renders callout tag with responsive collision classes when text is provided', () => {
    const wrapper = mount(ReaderBubbleOverlay, {
      props: {
        pageIndex: 5,
        targetBubble: {
          page: 5,
          box: [0.05, 0.75, 0.2, 0.95],
          text: '我的替身能力毫无破绽！',
        },
      },
    })

    const tag = wrapper.find('.bubble-callout')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('我的替身能力毫无破绽！')
    // 顶部 ymin < 0.12 翻转到底部
    expect(tag.classes()).toContain('is-placement-bottom')
    // 右侧 xmin > 0.65 靠右对齐
    expect(tag.classes()).toContain('is-align-right')

    expect(wrapper.attributes('aria-label')).toBe('命中对白：我的替身能力毫无破绽！')
  })

  it('omits callout tag when text is not provided', () => {
    const wrapper = mount(ReaderBubbleOverlay, {
      props: {
        pageIndex: 5,
        targetBubble: {
          page: 5,
          box: [0.15, 0.3, 0.25, 0.8],
        },
      },
    })

    expect(wrapper.find('.bubble-callout').exists()).toBe(false)
  })
})

import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import CoverCarousel from '@/components/CoverCarousel.vue'

describe('CoverCarousel', () => {
  const covers = ['/cover1.webp', '/cover2.webp', '/cover3.webp', '/cover4.webp']

  it('renders all cover slides and arrow buttons', () => {
    const wrapper = mount(CoverCarousel, {
      props: {
        covers,
        title: '测试漫画',
      },
    })

    const slides = wrapper.findAll('.cover-slide')
    expect(slides.length).toBe(4)
    expect(wrapper.findAll('.carousel-arrow').length).toBe(2)
  })

  it('scrolls into view when clicking next or prev arrows', async () => {
    const scrollIntoViewMock = vi.fn<() => void>()
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock

    const wrapper = mount(CoverCarousel, {
      props: {
        covers,
        title: '测试漫画',
      },
      attachTo: document.body,
    })

    const arrows = wrapper.findAll('.carousel-arrow')
    const rightArrow = arrows[1]!
    await rightArrow.trigger('click')

    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: 'smooth',
      inline: 'center',
      block: 'nearest',
    })

    wrapper.unmount()
  })

  it('scrolls target slide into view when clicking on a cover slide', async () => {
    const scrollIntoViewMock = vi.fn<() => void>()
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock

    const wrapper = mount(CoverCarousel, {
      props: {
        covers,
        title: '测试漫画',
      },
      attachTo: document.body,
    })

    const slides = wrapper.findAll('.cover-slide')
    // Click the 3rd slide (index 2)
    await slides[2]!.trigger('click')

    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: 'smooth',
      inline: 'center',
      block: 'nearest',
    })

    wrapper.unmount()
  })

  it('triggers centering on Enter and Space keypresses on slide', async () => {
    const scrollIntoViewMock = vi.fn<() => void>()
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock

    const wrapper = mount(CoverCarousel, {
      props: {
        covers,
        title: '测试漫画',
      },
      attachTo: document.body,
    })

    const slides = wrapper.findAll('.cover-slide')
    await slides[1]!.trigger('keydown.enter')
    expect(scrollIntoViewMock).toHaveBeenCalledTimes(1)

    await slides[3]!.trigger('keydown.space')
    expect(scrollIntoViewMock).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('hides arrow buttons when there is only one cover', () => {
    const wrapper = mount(CoverCarousel, {
      props: {
        covers: ['/single-cover.webp'],
        title: '单封面漫画',
      },
    })

    expect(wrapper.findAll('.cover-slide').length).toBe(1)
    expect(wrapper.find('.carousel-actions').exists()).toBe(false)
  })
})

import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TagManager from '@/components/form/TagManager.vue'

describe('TagManager', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders initial tags', () => {
    const wrapper = mount(TagManager, {
      props: {
        modelValue: ['全彩', 'Live2D'],
      },
    })
    const chips = wrapper.findAll('.tag-chip__text')
    expect(chips.length).toBe(2)
    expect(chips[0]!.text()).toBe('全彩')
    expect(chips[1]!.text()).toBe('Live2D')
  })

  it('removes tag on click delete', async () => {
    const wrapper = mount(TagManager, {
      props: {
        modelValue: ['全彩', 'Live2D'],
      },
    })
    const delBtns = wrapper.findAll('.tag-chip__del')
    await delBtns[0]!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]![0]).toEqual(['Live2D'])
  })

  it('adds new tag on enter', async () => {
    const wrapper = mount(TagManager, {
      props: {
        modelValue: ['全彩'],
      },
    })
    const input = wrapper.find('.tag-input-box')
    await input.setValue('精选')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]![0]).toEqual(['全彩', '精选'])
  })
})

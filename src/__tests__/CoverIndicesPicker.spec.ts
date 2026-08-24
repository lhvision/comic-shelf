import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import CoverIndicesPicker from '@/components/form/CoverIndicesPicker.vue'

describe('CoverIndicesPicker', () => {
  it('renders 4 inputs with default values', () => {
    const wrapper = mount(CoverIndicesPicker, {
      props: {
        modelValue: [1, 2, 3, 4],
        maxPage: 100,
      },
    })
    const inputs = wrapper.findAll('input')
    expect(inputs.length).toBe(4)
    expect((inputs[0]!.element as HTMLInputElement).value).toBe('1')
    expect((inputs[1]!.element as HTMLInputElement).value).toBe('2')
    expect((inputs[2]!.element as HTMLInputElement).value).toBe('3')
    expect((inputs[3]!.element as HTMLInputElement).value).toBe('4')
  })

  it('clamps values out of bounds on blur', async () => {
    const wrapper = mount(CoverIndicesPicker, {
      props: {
        modelValue: [1, 2, 3, 4],
        maxPage: 10,
      },
    })
    const inputs = wrapper.findAll('input')
    // Set first input to 999 (exceeds maxPage 10)
    await inputs[0]!.setValue(999)
    await inputs[0]!.trigger('blur')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    // Should fallback to slot default (1)
    const emitted = wrapper.emitted('update:modelValue')!
    const lastEmit = emitted[emitted.length - 1]![0] as number[]
    expect(lastEmit[0]).toBe(1)
  })

  it('handles negative or invalid numbers by restoring valid default', async () => {
    const wrapper = mount(CoverIndicesPicker, {
      props: {
        modelValue: [1, 2, 3, 4],
        maxPage: 50,
      },
    })
    const inputs = wrapper.findAll('input')
    await inputs[1]!.setValue(-5)
    await inputs[1]!.trigger('blur')
    const emitted = wrapper.emitted('update:modelValue')!
    const lastEmit = emitted[emitted.length - 1]![0] as number[]
    expect(lastEmit[1]).toBe(2)
  })
})

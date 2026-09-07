import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ImportRemoteTab from '@/components/import/ImportRemoteTab.vue'

describe('ImportRemoteTab Component', () => {
  it('renders prefix, placeholder, and binds aria-label properly', () => {
    const wrapper = mount(ImportRemoteTab, {
      props: {
        prefix: 'JM',
        placeholder: '523607',
        ariaLabel: '禁漫车号',
        tooltipId: 'test-tip',
        tooltipText: '测试提示',
        importing: false,
        canSubmit: true,
      },
    })

    expect(wrapper.find('.field-prefix').text()).toBe('JM')
    const input = wrapper.find('input')
    expect(input.attributes('placeholder')).toBe('523607')
    expect(input.attributes('aria-label')).toBe('禁漫车号')
    expect(wrapper.find('.vertical-text').text()).toBe('收录到纸间')
  })

  it('supports two-way binding on v-model:id and v-model:prefetchAll', async () => {
    const wrapper = mount(ImportRemoteTab, {
      props: {
        id: '',
        'onUpdate:id': (val: string) => wrapper.setProps({ id: val } as Record<string, unknown>),
        prefetchAll: false,
        'onUpdate:prefetchAll': (val: boolean) =>
          wrapper.setProps({ prefetchAll: val } as Record<string, unknown>),
        prefix: 'PICA',
        placeholder: '5ebe...',
        ariaLabel: '哔咔车号',
        tooltipId: 'test-tip',
        tooltipText: '测试提示',
        importing: false,
        canSubmit: true,
      },
    })

    const input = wrapper.find('input[type="text"]')
    await input.setValue('5ebe89bf63918511c2c362a7')
    expect(wrapper.emitted('update:id')?.[0]).toEqual(['5ebe89bf63918511c2c362a7'])

    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(true)
    expect(wrapper.emitted('update:prefetchAll')?.[0]).toEqual([true])
  })

  it('disables submit button when canSubmit is false or importing is true', async () => {
    const wrapper = mount(ImportRemoteTab, {
      props: {
        prefix: 'JM',
        placeholder: '523607',
        ariaLabel: '禁漫车号',
        tooltipId: 'test-tip',
        tooltipText: '测试提示',
        importing: false,
        canSubmit: false,
      },
    })

    const submitBtn = wrapper.find('.import-submit-btn')
    expect(submitBtn.attributes('disabled')).toBeDefined()

    await wrapper.setProps({ canSubmit: true, importing: true } as Record<string, unknown>)
    expect(submitBtn.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.vertical-text').text()).toBe('收录中…')

    await wrapper.setProps({ canSubmit: true, importing: false } as Record<string, unknown>)
    expect(submitBtn.attributes('disabled')).toBeUndefined()
  })

  it('emits submit event when form is submitted', async () => {
    const wrapper = mount(ImportRemoteTab, {
      props: {
        prefix: 'JM',
        placeholder: '523607',
        ariaLabel: '禁漫车号',
        tooltipId: 'test-tip',
        tooltipText: '测试提示',
        importing: false,
        canSubmit: true,
      },
    })

    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')?.length).toBe(1)
  })
})

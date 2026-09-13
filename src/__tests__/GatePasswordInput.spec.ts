import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import GatePasswordInput from '@/components/gate/GatePasswordInput.vue'

describe('GatePasswordInput.vue', () => {
  it('默认渲染密码输入框与锁头图标，初始为 password 类型', () => {
    const wrapper = mount(GatePasswordInput, {
      props: {
        placeholder: '输入口令',
      },
    })

    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)
    expect(input.attributes('type')).toBe('password')
    expect(input.attributes('placeholder')).toBe('输入口令')

    const icon = wrapper.findComponent({ name: 'AppIcon' })
    expect(icon.props('name')).toBe('lock')
  })

  it('点击小眼睛按钮可在明文与密文之间切换，并更新 aria-label', async () => {
    const wrapper = mount(GatePasswordInput, {
      props: {
        modelValue: 'secret123',
      },
    })

    const toggleBtn = wrapper.find('.btn-toggle-eye')
    expect(toggleBtn.exists()).toBe(true)
    expect(toggleBtn.attributes('aria-label')).toBe('显示口令')

    // 点击显示密码
    await toggleBtn.trigger('click')
    expect(wrapper.find('input').attributes('type')).toBe('text')
    expect(toggleBtn.attributes('aria-label')).toBe('隐藏口令')

    // 再次点击隐藏密码
    await toggleBtn.trigger('click')
    expect(wrapper.find('input').attributes('type')).toBe('password')
    expect(toggleBtn.attributes('aria-label')).toBe('显示口令')
  })

  it('支持 v-model 双向绑定', async () => {
    const wrapper = mount({
      components: { GatePasswordInput },
      setup() {
        const text = ref('')
        return { text }
      },
      template: '<GatePasswordInput v-model="text" />',
    })

    const input = wrapper.find('input')
    await input.setValue('my-password')
    expect(wrapper.vm.text).toBe('my-password')
  })

  it('传递 error 属性时，容器正确挂载 .error 样式类', () => {
    const wrapper = mount(GatePasswordInput, {
      props: {
        error: true,
      },
    })

    expect(wrapper.find('.input-wrap').classes()).toContain('error')
  })

  it('禁用态时，input 和切换按钮均置为 disabled', () => {
    const wrapper = mount(GatePasswordInput, {
      props: {
        disabled: true,
      },
    })

    expect(wrapper.find('input').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.btn-toggle-eye').attributes('disabled')).toBeDefined()
  })

  it('设置 monospace 或 inputmode="numeric" 时自动挂载 is-monospace 样式类', () => {
    const wrapperNumeric = mount(GatePasswordInput, {
      props: { inputmode: 'numeric' },
    })
    expect(wrapperNumeric.find('input').classes()).toContain('is-monospace')

    const wrapperMono = mount(GatePasswordInput, {
      props: { monospace: true },
    })
    expect(wrapperMono.find('input').classes()).toContain('is-monospace')

    const wrapperDefault = mount(GatePasswordInput)
    expect(wrapperDefault.find('input').classes()).not.toContain('is-monospace')
  })
})

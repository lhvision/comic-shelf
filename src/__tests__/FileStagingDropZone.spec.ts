import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import FileStagingDropZone from '@/components/form/FileStagingDropZone.vue'

describe('FileStagingDropZone.vue', () => {
  it('默认渲染网页上传拖拽区与文案', () => {
    const wrapper = mount(FileStagingDropZone, {
      props: {
        prompt: '测试拖拽提示',
        hint: '测试格式说明',
      },
    })

    expect(wrapper.find('.drop-zone').exists()).toBe(true)
    expect(wrapper.find('.drop-prompt').text()).toBe('测试拖拽提示')
    expect(wrapper.find('.drop-hint').text()).toBe('测试格式说明')
  })

  it('点击拖拽区调用 openFileDialog，在 disabled 状态下不触发', async () => {
    const openSpy = vi.fn<() => void>()
    const wrapper = mount(FileStagingDropZone, {
      props: {
        disabled: false,
        openFileDialog: openSpy,
      },
    })

    await wrapper.find('.drop-zone').trigger('click')
    expect(openSpy).toHaveBeenCalledTimes(1)

    // 切换到 disabled
    await wrapper.setProps({ disabled: true } as Record<string, unknown>)
    await wrapper.find('.drop-zone').trigger('click')
    expect(openSpy).toHaveBeenCalledTimes(1)
  })

  it('isOverDropZone 为 true 时，容器正确挂载 .is-dragover 类', () => {
    const wrapper = mount(FileStagingDropZone, {
      props: {
        isOverDropZone: true,
      },
    })

    expect(wrapper.find('.drop-zone').classes()).toContain('is-dragover')
  })

  it('有暂存文件时展示数量与首尾文件摘要，点击清空按钮清空列表并派发 clear 与 update:files 事件', async () => {
    const initialFiles = [
      new File(['1'], 'page_001.webp', { type: 'image/webp' }),
      new File(['2'], 'page_002.webp', { type: 'image/webp' }),
      new File(['3'], 'page_003.webp', { type: 'image/webp' }),
    ]

    const wrapper = mount(FileStagingDropZone, {
      props: {
        files: initialFiles,
      },
    })

    const summary = wrapper.find('.file-summary')
    expect(summary.exists()).toBe(true)
    expect(summary.text()).toContain('已就绪 3 张画页')
    expect(summary.text()).toContain('page_001.webp ~ page_003.webp')

    // 点击清空
    const clearBtn = wrapper.findComponent({ name: 'AppButton' })
    await clearBtn.trigger('click')

    expect(wrapper.emitted('clear')).toHaveLength(1)
    expect(wrapper.emitted('update:files')?.[0]).toEqual([[]])
  })

  it('切换至本地路径模式时，渲染路径输入框并支持双向绑定', async () => {
    const wrapper = mount(FileStagingDropZone, {
      props: {
        mode: 'path',
        serverPath: '',
      },
    })

    const input = wrapper.find('#staging-server-path')
    expect(input.exists()).toBe(true)

    await input.setValue('/data/comics/tiya')
    expect(wrapper.emitted('update:serverPath')?.[0]).toEqual(['/data/comics/tiya'])
  })

  it('showTabs 为 false 时隐藏双模切换 Tabs', () => {
    const wrapper = mount(FileStagingDropZone, {
      props: {
        showTabs: false,
      },
    })

    expect(wrapper.find('.mode-tabs-wrapper').exists()).toBe(false)
  })
})

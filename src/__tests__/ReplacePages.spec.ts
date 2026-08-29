import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DetailActionBar from '@/components/detail/DetailActionBar.vue'
import type { DropdownOption } from '@/types'

interface DetailActionBarVm {
  moreOptions: DropdownOption[]
  onMoreSelect: (option: DropdownOption) => void
}

describe('DetailActionBar - Replace Pages', () => {
  const baseProps = {
    title: '测试漫画',
    lastRead: 1,
    cachePercent: 100,
    caching: false,
    cacheComplete: true,
    cachedPages: 10,
    pageCount: 10,
    canWrite: true,
    source: 'jm',
    customPages: false,
  }

  it('renders replace_pages option in more dropdown when canWrite is true', () => {
    const wrapper = mount(DetailActionBar, { props: baseProps })
    const vm = wrapper.vm as unknown as DetailActionBarVm
    const replaceOpt = vm.moreOptions.find((o) => o.key === 'replace_pages')

    expect(replaceOpt).toBeDefined()
    expect(replaceOpt?.label).toContain('重新装订')
  })

  it('emits replacePages when replace_pages is selected', () => {
    const wrapper = mount(DetailActionBar, { props: baseProps })
    const vm = wrapper.vm as unknown as DetailActionBarVm
    vm.onMoreSelect({ key: 'replace_pages', label: '重新装订…' })

    expect(wrapper.emitted('replacePages')).toHaveLength(1)
  })

  it('shows protected label and disables cacheAll button when customPages is true', () => {
    const wrapper = mount(DetailActionBar, {
      props: {
        ...baseProps,
        customPages: true,
      },
    })

    const buttons = wrapper.findAll('button')
    const cacheBtn = buttons.find((b) => b.text().includes('已保护（重新装订）'))
    expect(cacheBtn).toBeDefined()
    expect(cacheBtn?.attributes('disabled')).toBeDefined()
  })
})

import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ChapterIndex from '@/components/detail/ChapterIndex.vue'
import type { Chapter } from '@/types'

vi.mock('@/components/detail/ChapterCard.vue', () => ({
  default: {
    name: 'ChapterCard',
    props: ['source', 'sourceId', 'chapter', 'cachedPages', 'running', 'busy'],
    template:
      '<div class="mock-chapter-card" :data-id="chapter.id">{{ chapter.title || chapter.index }}</div>',
  },
}))

vi.mock('@/components/AppIcon.vue', () => ({
  default: {
    name: 'AppIcon',
    props: ['name', 'size'],
    template: '<span class="mock-icon" :data-name="name" />',
  },
}))

function makeChapters(count: number): Chapter[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `chap_${i + 1}`,
    index: i + 1,
    title: `第 ${i + 1} 话`,
    start: i * 20 + 1,
    page_count: 20,
    cover_path: `/cover_${i + 1}.webp`,
  }))
}

describe('ChapterIndex', () => {
  it('renders initial 24 chapters and fold controls when count exceeds 24', async () => {
    const chapters = makeChapters(50)
    const wrapper = mount(ChapterIndex, {
      props: {
        source: 'jm',
        sourceId: '123456',
        chapters,
      },
    })

    // Initial visible chapters: 24
    expect(wrapper.findAll('.mock-chapter-card').length).toBe(24)

    // Bottom sentinel section shows remaining 26 chapters folded
    const sentinel = wrapper.find('.chapter-load-more-section')
    expect(sentinel.exists()).toBe(true)
    expect(sentinel.text()).toContain('余 26 话已折叠')
    expect(sentinel.text()).toContain('再展开 24 话')
    expect(sentinel.text()).toContain('展开全部')

    // At initial state, collapse button is hidden
    expect(sentinel.text()).not.toContain('收起目录')

    // Click "再展开 24 话"
    await sentinel.find('button.btn-primary').trigger('click')
    expect(wrapper.findAll('.mock-chapter-card').length).toBe(48)
    expect(sentinel.text()).toContain('余 2 话已折叠')
    expect(sentinel.text()).toContain('收起目录')

    // Click "收起目录"
    const collapseBtn = sentinel.findAll('button').find((b) => b.text().includes('收起目录'))
    expect(collapseBtn).toBeDefined()
    await collapseBtn!.trigger('click')

    // Reset back to initial 24
    expect(wrapper.findAll('.mock-chapter-card').length).toBe(24)
  })

  it('supports loadAll and shows collapse option when fully expanded', async () => {
    const chapters = makeChapters(30)
    const wrapper = mount(ChapterIndex, {
      props: {
        source: 'jm',
        sourceId: '123456',
        chapters,
      },
    })

    const sentinel = wrapper.find('.chapter-load-more-section')
    // Click "展开全部"
    const loadAllBtn = sentinel.findAll('button').find((b) => b.text().includes('展开全部'))
    expect(loadAllBtn).toBeDefined()
    await loadAllBtn!.trigger('click')

    expect(wrapper.findAll('.mock-chapter-card').length).toBe(30)
    expect(sentinel.text()).toContain('全目录已展开')

    // "收起目录" is available
    const collapseBtn = sentinel.findAll('button').find((b) => b.text().includes('收起目录'))
    expect(collapseBtn).toBeDefined()
    await collapseBtn!.trigger('click')

    expect(wrapper.findAll('.mock-chapter-card').length).toBe(24)
  })
})

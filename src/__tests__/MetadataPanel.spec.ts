import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import MetadataPanel from '@/components/MetadataPanel.vue'
import type { ComicMeta } from '@/types'

function makeMeta(partial: Partial<ComicMeta> = {}): ComicMeta {
  return {
    source: 'jm',
    source_id: '123456',
    display_id: 'JM123456',
    title: '测试漫画标题',
    authors: ['作者A'],
    works: ['原作B'],
    actors: ['角色C'],
    tags: ['同人', '汉化'],
    description: '',
    uploader: '测试上传者',
    page_count: 24,
    published_at: '2026-01-01',
    updated_at: '2026-01-02',
    views: '1000',
    likes: '200',
    comment_count: 10,
    favorite: false,
    cover_count: 4,
    source_url: 'https://example.com/comic/123456',
    pages: [],
    imported_at: '2026-01-01',
    last_checked_at: '2026-01-02',
    raw: {},
    ...partial,
  }
}

describe('MetadataPanel', () => {
  it('renders default fallback text when description is empty and does not show toggle button', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        meta: makeMeta({ description: '' }),
      },
    })

    expect(wrapper.find('.desc-toggle-btn').exists()).toBe(false)
    const content = wrapper.find('.description-content')
    expect(content.text()).toBe('原页面没有填写叙述。')
    expect(content.classes()).not.toContain('is-clamped')
    expect(content.classes()).not.toContain('is-expanded')
  })

  it('does not show toggle button when description is short (<= 3 lines and <= 90 chars)', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        meta: makeMeta({
          description: '第一行短简介\n第二行短简介\n第三行短简介',
        }),
      },
    })

    expect(wrapper.find('.desc-toggle-btn').exists()).toBe(false)
    const content = wrapper.find('.description-content')
    expect(content.classes()).not.toContain('is-clamped')
    expect(content.classes()).not.toContain('is-expanded')
  })

  it('renders toggle button and handles expand/collapse for long description (>90 chars)', async () => {
    const longText = '这是一段非常非常长的漫画叙述文字。'.repeat(6) // ~108 chars
    const wrapper = mount(MetadataPanel, {
      props: {
        meta: makeMeta({ description: longText }),
      },
    })

    const toggleBtn = wrapper.find('.desc-toggle-btn')
    expect(toggleBtn.exists()).toBe(true)
    expect(toggleBtn.attributes('aria-expanded')).toBe('false')
    expect(toggleBtn.attributes('aria-controls')).toBe('meta-description')
    expect(toggleBtn.text()).toContain('展开全文')

    const chevron = wrapper.find('.desc-chevron')
    expect(chevron.exists()).toBe(true)
    expect(chevron.classes()).not.toContain('is-rotated')

    const content = wrapper.find('.description-content')
    expect(content.attributes('id')).toBe('meta-description')
    expect(content.classes()).toContain('is-clamped')
    expect(content.classes()).not.toContain('is-expanded')

    // 点击展开
    await toggleBtn.trigger('click')

    expect(toggleBtn.attributes('aria-expanded')).toBe('true')
    expect(toggleBtn.text()).toContain('收起')
    expect(chevron.classes()).toContain('is-rotated')
    expect(content.classes()).toContain('is-expanded')
    expect(content.classes()).not.toContain('is-clamped')

    // 点击收起
    await toggleBtn.trigger('click')

    expect(toggleBtn.attributes('aria-expanded')).toBe('false')
    expect(toggleBtn.text()).toContain('展开全文')
    expect(chevron.classes()).not.toContain('is-rotated')
    expect(content.classes()).toContain('is-clamped')
    expect(content.classes()).not.toContain('is-expanded')
  })

  it('resets expanded state when switching comics via prop update', async () => {
    const longTextA = '这是漫画A的非常非常长的一段叙述文字内容。'.repeat(5)
    const longTextB = '这是漫画B的非常非常长的一段叙述文字内容。'.repeat(5)

    const wrapper = mount(MetadataPanel, {
      props: {
        meta: makeMeta({ display_id: 'JM001', description: longTextA }),
      },
    })

    const toggleBtn = wrapper.find('.desc-toggle-btn')
    // 展开漫画 A
    await toggleBtn.trigger('click')
    expect(wrapper.find('.description-content').classes()).toContain('is-expanded')

    // 切换到漫画 B
    await wrapper.setProps({
      meta: makeMeta({ display_id: 'JM002', description: longTextB }),
    } as Record<string, unknown>)

    // 应自动复位折叠
    expect(wrapper.find('.description-content').classes()).toContain('is-clamped')
    expect(wrapper.find('.description-content').classes()).not.toContain('is-expanded')
    expect(wrapper.find('.desc-toggle-btn').attributes('aria-expanded')).toBe('false')
  })

  it('renders toggle button when description has more than 3 line breaks', async () => {
    const multilineText = '第一行\n第二行\n第三行\n第四行'
    const wrapper = mount(MetadataPanel, {
      props: {
        meta: makeMeta({ description: multilineText }),
      },
    })

    const toggleBtn = wrapper.find('.desc-toggle-btn')
    expect(toggleBtn.exists()).toBe(true)
    const content = wrapper.find('.description-content')
    expect(content.classes()).toContain('is-clamped')
  })
})

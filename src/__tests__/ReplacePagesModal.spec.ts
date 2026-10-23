import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ReplacePagesModal from '@/components/detail/ReplacePagesModal.vue'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'
import { api } from '@/api/client'
import type { ComicDetail, ComicMeta } from '@/types'

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

const mockBroadcastLocalChange = vi.fn<(...args: unknown[]) => void>()
vi.mock('@/composables/useSystemEvents', () => ({
  useSystemEvents: () => ({ broadcastLocalChange: mockBroadcastLocalChange }),
}))

vi.mock('@/api/client', () => ({
  api: {
    replaceComicPages: vi.fn<typeof api.replaceComicPages>(),
    replaceComicPagesFromPath: vi.fn<typeof api.replaceComicPagesFromPath>(),
  },
}))

describe('ReplacePagesModal Component', () => {
  const baseMeta: ComicMeta = {
    source: 'local',
    source_id: 'test1234',
    display_id: 'LOC_test1234',
    title: '测试漫画',
    authors: ['作者'],
    works: [],
    actors: [],
    tags: [],
    description: '',
    uploader: null,
    page_count: 20,
    published_at: '2026-01-01',
    updated_at: '2026-01-01',
    views: '0',
    likes: '0',
    comment_count: 0,
    favorite: false,
    cover_count: 1,
    source_url: '',
    pages: [],
    imported_at: '2026-01-01',
    last_checked_at: '2026-01-01',
    raw: {},
    chapters: [
      { id: 'ch1', title: '第 1 话', index: 1, page_count: 10, start: 1 },
      { id: 'ch2', title: '第 2 话', index: 2, page_count: 10, start: 11 },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  function createWrapper(propsData = {}) {
    return mount(ReplacePagesModal, {
      props: {
        open: true,
        meta: baseMeta,
        ...propsData,
      },
      global: {
        stubs: {
          Teleport: true,
          AppIcon: {
            template: '<span class="app-icon" :data-name="name" />',
            props: ['name'],
          },
          FileStagingDropZone: {
            template: '<div class="file-staging-stub" />',
            props: ['mode', 'files', 'serverPath', 'disabled'],
          },
        },
      },
    })
  }

  it('renders default state with preventClose=false and cancel button enabled', () => {
    const wrapper = createWrapper()
    const modal = wrapper.findComponent(Modal)
    expect(modal.exists()).toBe(true)
    const modalProps = modal.props() as Record<string, unknown>
    expect(modalProps.preventClose).toBe(false)

    const buttons = wrapper.findAllComponents(AppButton)
    const cancelBtn = buttons.find((b) => b.text().includes('取消'))
    const cancelProps = cancelBtn?.props() as Record<string, unknown> | undefined
    expect(cancelProps?.disabled).toBe(false)

    const submitBtn = buttons.find((b) => b.text().includes('确认重新装订'))
    expect(submitBtn?.exists()).toBe(true)
  })

  it('emits cancel when cancel button is clicked while not submitting', async () => {
    const wrapper = createWrapper()
    const buttons = wrapper.findAllComponents(AppButton)
    const cancelBtn = buttons.find((b) => b.text().includes('取消'))
    expect(cancelBtn).toBeDefined()

    await cancelBtn!.trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })

  it('locks modal with preventClose=true and disables cancel button while submitting', async () => {
    let resolveApi!: (value: ComicDetail) => void
    const pendingPromise = new Promise<ComicDetail>((resolve) => {
      resolveApi = resolve
    })
    vi.mocked(api.replaceComicPagesFromPath).mockReturnValue(pendingPromise)

    const wrapper = createWrapper()

    // Switch to path mode
    const vm = wrapper.vm as unknown as {
      mode: string
      serverPath: string
      ackReplace: boolean
    }
    vm.mode = 'path'
    vm.serverPath = '/valid/path'
    vm.ackReplace = true
    await nextTick()

    // Trigger submit
    const submitBtn = wrapper
      .findAllComponents(AppButton)
      .find((b) => b.text().includes('确认重新装订'))
    await submitBtn!.trigger('click')
    await nextTick()

    // Submitting state should now be active
    const modal = wrapper.findComponent(Modal)
    const modalProps = modal.props() as Record<string, unknown>
    expect(modalProps.preventClose).toBe(true)

    const buttons = wrapper.findAllComponents(AppButton)
    const cancelBtn = buttons.find((b) => b.text().includes('取消'))
    const cancelProps = cancelBtn?.props() as Record<string, unknown> | undefined
    expect(cancelProps?.disabled).toBe(true)

    // Submit button displays loading state and spinner
    const activeSubmitBtn = buttons.find((b) => {
      const p = b.props() as Record<string, unknown>
      return p.loading === true
    })
    expect(activeSubmitBtn?.exists()).toBe(true)
    expect(activeSubmitBtn?.find('.btn-spinner').exists()).toBe(true)

    // Attempting to invoke cancel during submitting is safely blocked
    await cancelBtn!.trigger('click')
    expect(wrapper.emitted('cancel')).toBeUndefined()

    // Re-entrancy guard: Triggering submit again during submission is blocked
    await submitBtn!.trigger('click')
    expect(api.replaceComicPagesFromPath).toHaveBeenCalledTimes(1)

    // Resolve API call
    resolveApi({ meta: baseMeta } as ComicDetail)
    await nextTick()
    await nextTick()

    const updatedModalProps = modal.props() as Record<string, unknown>
    expect(updatedModalProps.preventClose).toBe(false)
    expect(wrapper.emitted('replaced')).toHaveLength(1)
  })
})

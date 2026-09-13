/**
 * @file useChapterManagement.ts
 * @description 章节管理组合式函数（编辑标题、删除章节、更多菜单编排）。
 *
 * 遵循 docs/agents/frontend.md 规范：
 * - 视图轻量化（View Thinness）：将弹窗交互与 API 调用下沉至 composable；
 * - 精准解构与契约自解释。
 */

import { computed, ref, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { useLibraryStore } from '@/stores/library'
import type { Chapter, ComicDetail, DropdownOption } from '@/types'

export interface UseChapterManagementOptions {
  /** 漫画来源渠道 */
  source: Ref<string>
  /** 漫画作品 ID */
  sourceId: Ref<string>
  /** 当前激活章节对象引用 */
  activeChapter: Ref<Chapter | null>
  /** 章节元数据成功更新后的回调 */
  onDetailUpdated?: (detail: ComicDetail) => void
}

export function useChapterManagement(options: UseChapterManagementOptions) {
  const { source, sourceId, activeChapter, onDetailUpdated } = options
  const router = useRouter()
  const store = useLibraryStore()
  const { toast } = useToast()
  const { broadcastLocalChange } = useSystemEvents()

  // 编辑章节标题弹窗状态
  const editOpen = ref(false)
  const chapterTitleInput = ref('')
  const savingTitle = ref(false)

  // 删除章节二次确认弹窗状态
  const removeOpen = ref(false)
  const ackRemove = ref(false)
  const removing = ref(false)

  const chapterMoreOptions = computed<DropdownOption[]>(() => [
    {
      key: 'remove',
      label: '删除本话…',
      danger: true,
      hint: '不可撤销',
    },
  ])

  function onChapterMoreSelect(option: DropdownOption) {
    if (option.key === 'remove') {
      requestRemoveChapter()
    }
  }

  function openEditModal() {
    chapterTitleInput.value = activeChapter.value?.title || ''
    editOpen.value = true
  }

  async function saveChapterTitle() {
    if (!activeChapter.value) return
    savingTitle.value = true
    try {
      const updated = await api.updateChapter(
        source.value,
        sourceId.value,
        activeChapter.value.id,
        chapterTitleInput.value,
      )
      onDetailUpdated?.(updated)
      store.setDetail(updated)
      editOpen.value = false
      toast('章节名称已更新', 'success')
      broadcastLocalChange({
        action: 'update_chapter',
        source: source.value,
        source_id: sourceId.value,
        chapter_id: activeChapter.value.id,
        timestamp: Date.now(),
      })
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      savingTitle.value = false
    }
  }

  function requestRemoveChapter() {
    ackRemove.value = false
    removeOpen.value = true
  }

  async function confirmRemoveChapter() {
    if (!activeChapter.value) return
    removing.value = true
    const deletedId = activeChapter.value.id
    const deletedTitle = activeChapter.value.title || `第 ${activeChapter.value.index} 话`
    try {
      await api.deleteChapter(source.value, sourceId.value, deletedId)
      store.removeDetail(source.value, sourceId.value)
      removeOpen.value = false
      toast(`已删除「${deletedTitle}」`, 'success')
      broadcastLocalChange({
        action: 'delete_chapter',
        source: source.value,
        source_id: sourceId.value,
        chapter_id: deletedId,
        timestamp: Date.now(),
      })
      void router.replace(`/comic/${source.value}/${sourceId.value}`)
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      removing.value = false
    }
  }

  return {
    editOpen,
    chapterTitleInput,
    savingTitle,
    removeOpen,
    ackRemove,
    removing,
    chapterMoreOptions,
    onChapterMoreSelect,
    openEditModal,
    saveChapterTitle,
    requestRemoveChapter,
    confirmRemoveChapter,
  }
}

import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useFileDialog, useDropZone } from '@vueuse/core'
import { api } from '@/api/client'
import { useLibraryStore } from '@/stores/library'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useUploadQueue } from '@/composables/useUploadQueue'
import { filterImageFiles, naturalSortFiles } from '@/composables/useFileStaging'
import type { LocalChapterInput } from '@/types'

export interface StagedChapter {
  id: string
  title: string
  files: File[]
}

export function useLocalWorkshop() {
  const router = useRouter()
  const store = useLibraryStore()
  const { canWrite } = useAuth()
  const { toast } = useToast()
  const { isUploading, progress, completedCount, totalCount, uploadFiles } = useUploadQueue()

  onMounted(() => {
    if (!canWrite.value) {
      toast('访客模式下无法进入自建工坊，请先解锁馆长权限', 'error')
      void router.replace('/')
    }
  })

  const mode = ref<'upload' | 'path'>('upload')
  const modeTabs = [
    { key: 'upload' as const, label: '网页多图上传' },
    { key: 'path' as const, label: '服务器目录导入' },
  ]
  const isMulti = ref(false)

  // Form fields
  const slugId = ref('')
  const title = ref('')
  const works = ref('')
  const authors = ref('自制')
  const actors = ref('')
  const uploader = ref('lhvision')
  const description = ref('')
  const tags = ref<string[]>([])
  const serverPath = ref('')
  const coverIndices = ref<number[]>([1, 2, 3, 4])
  const submitting = ref(false)

  // Staged chapters
  const activeChapterIdx = ref(0)
  const chapters = ref<StagedChapter[]>([{ id: 'ch1', title: '第 1 话', files: [] }])
  const singleFiles = ref<File[]>([])

  // DropZone & FileDialog via VueUse
  const dropAreaRef = ref<HTMLElement | null>(null)

  function stageFiles(rawList: File[]) {
    const { valid } = filterImageFiles(rawList)
    if (isMulti.value) {
      const ch = chapters.value[activeChapterIdx.value]
      if (ch) {
        ch.files = naturalSortFiles([...ch.files, ...valid])
      }
    } else {
      singleFiles.value = naturalSortFiles([...singleFiles.value, ...valid])
    }
  }

  const { open: openFileDialog, onChange: onFileDialogChange } = useFileDialog({
    multiple: true,
    accept: 'image/*',
    reset: true,
  })

  onFileDialogChange((files) => {
    if (files) stageFiles(Array.from(files))
  })

  const { isOverDropZone } = useDropZone(dropAreaRef, {
    onDrop: (files) => {
      if (files) stageFiles(files)
    },
  })

  function addChapter() {
    const nextIdx = chapters.value.length + 1
    chapters.value.push({
      id: `ch${nextIdx}`,
      title: `第 ${nextIdx} 话`,
      files: [],
    })
    activeChapterIdx.value = chapters.value.length - 1
  }

  function removeChapter(idx: number) {
    if (chapters.value.length <= 1) return
    chapters.value.splice(idx, 1)
    if (activeChapterIdx.value >= chapters.value.length) {
      activeChapterIdx.value = chapters.value.length - 1
    }
  }

  function clearCurrentStaged() {
    if (isMulti.value) {
      const current = chapters.value[activeChapterIdx.value]
      if (current) current.files = []
    } else {
      singleFiles.value = []
    }
  }

  const totalStagedFilesCount = computed(() => {
    if (!isMulti.value) return singleFiles.value.length
    return chapters.value.reduce((acc, ch) => acc + ch.files.length, 0)
  })

  function parseList(str: string): string[] {
    return str
      .split(/[/,，、]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }

  async function submit() {
    if (!title.value.trim()) {
      toast('请输入作品标题', 'error')
      return
    }

    if (mode.value === 'path') {
      if (!serverPath.value.trim()) {
        toast('请输入服务器目录路径', 'error')
        return
      }
      submitting.value = true
      try {
        const res = await api.importLocalPath({
          path: serverPath.value.trim(),
          id: slugId.value.trim() || undefined,
          title: title.value.trim(),
          works: parseList(works.value),
          authors: parseList(authors.value),
          actors: parseList(actors.value),
          tags: tags.value,
          description: description.value.trim(),
          uploader: uploader.value.trim() || '本地导入',
          cover_indices: coverIndices.value,
        })
        await store.load()
        toast('本地目录已收录', 'info')
        void router.push(`/comic/${res.meta.source}/${res.meta.source_id}`)
      } catch (err) {
        toast(err instanceof Error ? err.message : String(err), 'error')
      } finally {
        submitting.value = false
      }
      return
    }

    // Upload mode
    if (totalStagedFilesCount.value === 0) {
      toast('请先选择或拖入图片文件', 'error')
      return
    }

    submitting.value = true
    try {
      const chapterInputs: LocalChapterInput[] = isMulti.value
        ? chapters.value.map((c) => ({ id: c.id, title: c.title }))
        : []

      // 1. Create base metadata
      const created = await api.createLocalComic({
        id: slugId.value.trim() || undefined,
        title: title.value.trim(),
        works: parseList(works.value),
        authors: parseList(authors.value),
        actors: parseList(actors.value),
        tags: tags.value,
        description: description.value.trim(),
        uploader: uploader.value.trim() || '自制',
        chapters: chapterInputs,
        cover_indices: coverIndices.value,
      })

      const sourceId = created.meta.source_id

      // 2. Upload files via controlled queue
      if (isMulti.value) {
        for (const ch of chapters.value) {
          if (ch.files.length > 0) {
            await uploadFiles(sourceId, ch.files, ch.id, ch.title)
          }
        }
      } else {
        await uploadFiles(sourceId, singleFiles.value, '', '')
      }

      await store.load()
      toast(`自建图集《${created.meta.title}》已成功收录！`, 'info')
      void router.push(`/comic/${created.meta.source}/${sourceId}`)
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'error')
    } finally {
      submitting.value = false
    }
  }

  return {
    mode,
    modeTabs,
    isMulti,
    slugId,
    title,
    works,
    authors,
    actors,
    uploader,
    description,
    tags,
    serverPath,
    coverIndices,
    submitting,
    activeChapterIdx,
    chapters,
    singleFiles,
    dropAreaRef,
    isOverDropZone,
    openFileDialog,
    addChapter,
    removeChapter,
    clearCurrentStaged,
    totalStagedFilesCount,
    isUploading,
    progress,
    completedCount,
    totalCount,
    submit,
  }
}

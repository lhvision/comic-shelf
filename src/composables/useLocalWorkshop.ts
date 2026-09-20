import { computed, ref, onMounted, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useFileDialog, useDropZone } from '@vueuse/core'
import { api } from '@/api/client'
import { useLibraryStore } from '@/stores/library'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useSystemEvents } from '@/composables/useSystemEvents'
import { useUploadQueue } from '@/composables/useUploadQueue'
import { filterImageFiles, isPdfFile, naturalSortFiles } from '@/composables/useFileStaging'
import { sumBy } from '@/utils/math'
import { formatLocalImportToast } from '@/utils/format'
import type { ComicDetail, LocalChapterInput, PdfInspectResponse } from '@/types'

export interface StagedChapter {
  id: string
  title: string
  files: File[]
}

export interface UseLocalWorkshopOptions {
  /** 外部传入的拖拽接收 DOM 容器 Ref（如通过 Vue 3.5 useTemplateRef 获取） */
  dropAreaRef?: Readonly<Ref<HTMLElement | null>> | Ref<HTMLElement | null>
}

/**
 * 封面页码上限：暂存 PDF 用总页数；路径导入未知页数时不封顶；网页上传用已暂存张数。
 *
 * @param stagedPdfTotalPages 暂存 PDF 的总页数；无 PDF 时传 `null`
 * @param mode 工坊当前模式
 * @param stagedFilesCount 已暂存图片张数（上传模式）
 */
export function resolveCoverMaxPage(
  stagedPdfTotalPages: number | null,
  mode: 'upload' | 'path',
  stagedFilesCount: number,
): number | null {
  if (stagedPdfTotalPages != null) return stagedPdfTotalPages
  if (mode === 'path') return null
  return stagedFilesCount || 1
}

export function useLocalWorkshop(options: UseLocalWorkshopOptions = {}) {
  const router = useRouter()
  const store = useLibraryStore()
  const { canWrite } = useAuth()
  const { toast } = useToast()
  const { broadcastLocalChange } = useSystemEvents()
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

  // PDF inspection state
  const isInspectingPdf = ref(false)
  const stagedPdfMeta = ref<PdfInspectResponse | null>(null)

  // Staged chapters
  const activeChapterIdx = ref(0)
  const chapters = ref<StagedChapter[]>([{ id: 'ch1', title: '第 1 话', files: [] }])
  const singleFiles = ref<File[]>([])

  // DropZone & FileDialog via VueUse
  const dropAreaRef = options.dropAreaRef ?? ref<HTMLElement | null>(null)

  async function inspectPdfFile(pdfFile: File) {
    isInspectingPdf.value = true
    try {
      const fd = new FormData()
      fd.append('file', pdfFile)
      const res = await api.inspectPdf(fd)
      stagedPdfMeta.value = res
      if (!title.value.trim() && res.title) {
        title.value = res.title
      }
      if (res.authors.length > 0 && authors.value === '自制') {
        authors.value = res.authors.join(', ')
      }
      isMulti.value = res.chapters.length > 1
      chapters.value = res.chapters.map((c) => ({
        id: c.id,
        title: c.title,
        files: Array.from({ length: c.page_count }, () => null as unknown as File),
      }))
      activeChapterIdx.value = 0
      const trackLabel =
        res.detection_track === 'toc'
          ? '电子书签'
          : res.detection_track === 'ocr'
            ? 'OCR扉页探测'
            : '单卷平铺'
      toast(
        `成功解析 PDF：全书 ${res.total_pages} 页，已按${trackLabel}切分为 ${res.chapters.length} 话`,
        'info',
      )
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'error')
    } finally {
      isInspectingPdf.value = false
    }
  }

  async function inspectServerPdf() {
    if (!serverPath.value.trim()) {
      toast('请输入服务器 PDF 文件路径', 'error')
      return
    }
    isInspectingPdf.value = true
    try {
      const fd = new FormData()
      fd.append('server_path', serverPath.value.trim())
      const res = await api.inspectPdf(fd)
      stagedPdfMeta.value = res
      if (!title.value.trim() && res.title) {
        title.value = res.title
      }
      if (res.authors.length > 0 && authors.value === '自制') {
        authors.value = res.authors.join(', ')
      }
      isMulti.value = res.chapters.length > 1
      chapters.value = res.chapters.map((c) => ({
        id: c.id,
        title: c.title,
        files: Array.from({ length: c.page_count }, () => null as unknown as File),
      }))
      activeChapterIdx.value = 0
      const trackLabel =
        res.detection_track === 'toc'
          ? '电子书签'
          : res.detection_track === 'ocr'
            ? 'OCR扉页探测'
            : '单卷平铺'
      toast(
        `成功解析 PDF：全书 ${res.total_pages} 页，已按${trackLabel}切分为 ${res.chapters.length} 话`,
        'info',
      )
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'error')
    } finally {
      isInspectingPdf.value = false
    }
  }

  function clearStagedPdf() {
    const token = stagedPdfMeta.value?.staging_token
    if (token) {
      void api.deleteStagedPdf(token).catch(() => {})
    }
    stagedPdfMeta.value = null
    chapters.value = [{ id: 'ch1', title: '第 1 话', files: [] }]
    activeChapterIdx.value = 0
    singleFiles.value = []
    isMulti.value = false
    toast('已重置 PDF 暂存状态', 'info')
  }

  function stageFiles(rawList: File[]) {
    const pdf = rawList.find(isPdfFile)
    if (pdf) {
      void inspectPdfFile(pdf)
      return
    }
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
    accept: 'image/*,application/pdf,.pdf',
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
    if (stagedPdfMeta.value) {
      const removed = chapters.value[idx]
      const mergeTargetIdx = idx > 0 ? idx - 1 : 1
      const target = chapters.value[mergeTargetIdx]
      if (target && removed) {
        target.files = Array.from(
          { length: target.files.length + removed.files.length },
          () => null as unknown as File,
        )
      }
    }
    chapters.value.splice(idx, 1)
    if (activeChapterIdx.value >= chapters.value.length) {
      activeChapterIdx.value = chapters.value.length - 1
    }
  }

  const chapterRanges = computed(() => {
    let cursor = 1
    return chapters.value.map((ch) => {
      const count = ch.files.length
      const start = cursor
      const end = start + Math.max(0, count - 1)
      cursor += count
      return { id: ch.id, start, end, count }
    })
  })

  function clearCurrentStaged() {
    if (stagedPdfMeta.value) {
      toast('PDF 暂存模式下无法单独清空单话，如需重置请点击「重置暂存」', 'info')
      return
    }
    if (isMulti.value) {
      const current = chapters.value[activeChapterIdx.value]
      if (current) current.files = []
    } else {
      singleFiles.value = []
    }
  }

  const totalStagedFilesCount = computed(() => {
    if (stagedPdfMeta.value) {
      return stagedPdfMeta.value.total_pages
    }
    if (!isMulti.value) return singleFiles.value.length
    return sumBy(chapters.value, (ch) => ch.files.length)
  })

  /**
   * 封面页码上限。路径导入时尚未知道画页总数，传 `null` 表示不封顶，避免被卡成 1/1/1/1。
   */
  const coverMaxPage = computed<number | null>(() =>
    resolveCoverMaxPage(
      stagedPdfMeta.value ? stagedPdfMeta.value.total_pages : null,
      mode.value,
      totalStagedFilesCount.value,
    ),
  )

  const currentChapterFiles = computed<File[]>({
    get: () =>
      isMulti.value ? (chapters.value[activeChapterIdx.value]?.files ?? []) : singleFiles.value,
    set: (val) => {
      if (isMulti.value) {
        const ch = chapters.value[activeChapterIdx.value]
        if (ch) ch.files = val
      } else {
        singleFiles.value = val
      }
    },
  })

  function parseList(str: string): string[] {
    return str
      .split(/[/,，、]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }

  function buildCommonMetadata(defaultUploader: string) {
    return {
      id: slugId.value.trim() || undefined,
      title: title.value.trim(),
      works: parseList(works.value),
      authors: parseList(authors.value),
      actors: parseList(actors.value),
      tags: tags.value,
      description: description.value.trim(),
      uploader: uploader.value.trim() || defaultUploader,
      cover_indices: coverIndices.value,
    }
  }

  async function finishImport(comic: ComicDetail, kindLabel?: string): Promise<void> {
    const sourceId = comic.meta.source_id
    await store.load()
    broadcastLocalChange({
      action: 'import',
      source: comic.meta.source,
      source_id: sourceId,
      timestamp: Date.now(),
    })
    toast(formatLocalImportToast(comic.meta, kindLabel), 'info')
    void router.replace(`/comic/${comic.meta.source}/${sourceId}`)
  }

  async function submit() {
    if (!title.value.trim()) {
      toast('请输入作品标题', 'error')
      return
    }

    if (stagedPdfMeta.value) {
      const totalAssignedPages = sumBy(chapters.value, (ch) => ch.files.length)
      if (totalAssignedPages !== stagedPdfMeta.value.total_pages) {
        toast(
          `章节分配总页数（${totalAssignedPages}P）与 PDF 实际页数（${stagedPdfMeta.value.total_pages}P）不一致，请重置后重试`,
          'error',
        )
        return
      }
      submitting.value = true
      try {
        const created = await api.createFromStagedPdf({
          staging_token: stagedPdfMeta.value.staging_token,
          ...buildCommonMetadata('PDF导入'),
          chapters: (() => {
            let cursor = 1
            return chapters.value.map((ch, idx) => {
              const count = Math.max(1, ch.files.length)
              const start = cursor
              cursor += count
              return {
                id: ch.id,
                index: idx + 1,
                title: ch.title,
                start,
                page_count: count,
              }
            })
          })(),
        })
        await finishImport(created, 'PDF 漫画')
      } catch (err) {
        toast(err instanceof Error ? err.message : String(err), 'error')
      } finally {
        submitting.value = false
      }
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
          ...buildCommonMetadata('本地导入'),
        })
        await finishImport(res)
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
        ...buildCommonMetadata('自制'),
        chapters: chapterInputs,
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

      await finishImport(created)
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
    currentChapterFiles,
    dropAreaRef,
    isOverDropZone,
    openFileDialog,
    addChapter,
    removeChapter,
    clearCurrentStaged,
    totalStagedFilesCount,
    coverMaxPage,
    chapterRanges,
    isUploading,
    progress,
    completedCount,
    totalCount,
    submit,
    isInspectingPdf,
    stagedPdfMeta,
    inspectPdfFile,
    inspectServerPdf,
    clearStagedPdf,
  }
}

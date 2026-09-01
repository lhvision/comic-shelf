import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { naturalSortFiles, filterImageFiles, useFileStaging } from '@/composables/useFileStaging'

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

describe('useFileStaging', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('naturalSortFiles sorts numerically and alphanumerically', () => {
    const f1 = new File([''], 'page10.png')
    const f2 = new File([''], 'page2.png')
    const f3 = new File([''], 'page1.png')
    const sorted = naturalSortFiles([f1, f2, f3])
    expect(sorted.map((f) => f.name)).toEqual(['page1.png', 'page2.png', 'page10.png'])
  })

  it('filterImageFiles filters non-image files and counts ignored files', () => {
    const f1 = new File([''], 'page1.jpg')
    const f2 = new File([''], 'readme.txt')
    const f3 = new File([''], 'thumb.webp')
    const { valid, ignoredCount } = filterImageFiles([f1, f2, f3])
    expect(valid.map((f) => f.name)).toEqual(['page1.jpg', 'thumb.webp'])
    expect(ignoredCount).toBe(1)
  })

  it('stageFiles handles deduplication and removal', () => {
    const { files, stageFiles, removeFile, clearFiles } = useFileStaging({ deduplicate: true })
    const f1 = new File(['hello'], 'page1.jpg')
    const f2 = new File(['world'], 'page2.png')
    stageFiles([f1, f2])
    expect(files.value.length).toBe(2)

    // Staging same file again deduplicates
    stageFiles([f1])
    expect(files.value.length).toBe(2)

    // Remove one
    removeFile(0)
    expect(files.value.length).toBe(1)

    // Clear
    clearFiles()
    expect(files.value.length).toBe(0)
  })

  it('respects disabled state and ignores staging', () => {
    const { files, stageFiles } = useFileStaging({ disabled: true })
    const f1 = new File(['hello'], 'page1.jpg')
    stageFiles([f1])
    expect(files.value.length).toBe(0)
  })
})

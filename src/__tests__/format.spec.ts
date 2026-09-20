import { describe, it, expect } from 'vite-plus/test'
import { formatBytes, formatLocalImportToast } from '@/utils/format'

describe('format utility module', () => {
  describe('formatLocalImportToast', () => {
    it('includes title, display_id and page count', () => {
      expect(
        formatLocalImportToast({
          title: '2899054',
          display_id: 'LOC_2899054',
          page_count: 12,
        }),
      ).toBe('已收录《2899054》（LOC_2899054，共 12 页）')
    })

    it('omits page count when the album is still empty', () => {
      expect(
        formatLocalImportToast({
          title: '缇雅拆帧',
          display_id: 'LOC_20260920_143025',
          page_count: 0,
        }),
      ).toBe('已收录《缇雅拆帧》（LOC_20260920_143025）')
    })

    it('prefixes PDF imports', () => {
      expect(
        formatLocalImportToast(
          {
            title: '单行本',
            display_id: 'LOC_oneshot',
            page_count: 180,
          },
          'PDF 漫画',
        ),
      ).toBe('已收录 PDF 漫画《单行本》（LOC_oneshot，共 180 页）')
    })
  })

  describe('formatBytes', () => {
    it('formats 0 and negative bytes as 0 B', () => {
      expect(formatBytes(0)).toBe('0 B')
      expect(formatBytes(-100)).toBe('0 B')
      expect(formatBytes(Number.NaN)).toBe('0 B')
    })

    it('formats bytes, KB, MB, GB accurately', () => {
      expect(formatBytes(512)).toBe('512 B')
      expect(formatBytes(1024)).toBe('1.0 KB')
      expect(formatBytes(1024 * 1.5)).toBe('1.5 KB')
      expect(formatBytes(1024 * 1024 * 3.4)).toBe('3.4 MB')
      expect(formatBytes(1024 * 1024 * 1024 * 4.5)).toBe('4.5 GB')
    })
  })
})

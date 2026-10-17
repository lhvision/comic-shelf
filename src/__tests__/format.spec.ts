import { describe, it, expect } from 'vite-plus/test'
import {
  formatBytes,
  formatDateTime,
  formatLocalImportToast,
  formatRelativeTime,
  parseDateToMs,
} from '@/utils/format'

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

  describe('parseDateToMs and formatDateTime', () => {
    it('handles falsy or invalid input', () => {
      expect(parseDateToMs(null)).toBe(0)
      expect(parseDateToMs('')).toBe(0)
      expect(parseDateToMs('invalid-date')).toBe(0)
      expect(formatDateTime(null)).toBe('')
      expect(formatDateTime('')).toBe('')
      expect(formatDateTime('invalid')).toBe('')
    })

    it('parses numeric timestamps (seconds and milliseconds)', () => {
      const tsSec = 1760690911
      expect(parseDateToMs(tsSec)).toBe(tsSec * 1000)
      expect(parseDateToMs(String(tsSec))).toBe(tsSec * 1000)
      const tsMs = 1760690911000
      expect(parseDateToMs(tsMs)).toBe(tsMs)
      expect(parseDateToMs(String(tsMs))).toBe(tsMs)
    })

    it('parses ISO 8601 UTC strings', () => {
      const iso = '2026-10-17T08:48:31.000Z'
      const ms = parseDateToMs(iso)
      expect(ms).toBe(Date.parse(iso))
      expect(formatDateTime(iso)).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
    })

    it('parses legacy space-separated time strings assuming UTC', () => {
      const legacy = '2026-10-17 08:48:31'
      const ms = parseDateToMs(legacy)
      expect(ms).toBe(Date.parse('2026-10-17T08:48:31Z'))

      const legacyWithMs = '2026-10-17 08:48:31.456'
      const msWithFrac = parseDateToMs(legacyWithMs)
      expect(msWithFrac).toBe(Date.parse('2026-10-17T08:48:31.456Z'))
    })
  })

  describe('formatRelativeTime', () => {
    it('returns "从未" for empty or invalid input', () => {
      expect(formatRelativeTime(null)).toBe('从未')
      expect(formatRelativeTime('')).toBe('从未')
    })

    it('returns human readable relative time based on diff', () => {
      const now = Date.now()
      expect(formatRelativeTime(now - 10 * 1000)).toBe('刚刚')
      expect(formatRelativeTime(now - 120 * 1000)).toBe('2 分钟前')
      expect(formatRelativeTime(now - 7200 * 1000)).toBe('2 小时前')
      expect(formatRelativeTime(now - 86400 * 2 * 1000)).toBe('2 天前')
    })
  })
})

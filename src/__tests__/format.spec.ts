import { describe, it, expect } from 'vite-plus/test'
import { formatBytes } from '@/utils/format'

describe('format utility module', () => {
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

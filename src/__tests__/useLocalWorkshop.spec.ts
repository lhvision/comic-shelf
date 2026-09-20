import { describe, it, expect } from 'vite-plus/test'
import { resolveCoverMaxPage } from '@/composables/useLocalWorkshop'

describe('resolveCoverMaxPage', () => {
  it('uses staged PDF page count when a PDF is ready', () => {
    expect(resolveCoverMaxPage(180, 'path', 0)).toBe(180)
    expect(resolveCoverMaxPage(12, 'upload', 3)).toBe(12)
  })

  it('does not cap path imports when page count is unknown', () => {
    expect(resolveCoverMaxPage(null, 'path', 0)).toBeNull()
  })

  it('uses staged file count for web uploads, falling back to 1', () => {
    expect(resolveCoverMaxPage(null, 'upload', 24)).toBe(24)
    expect(resolveCoverMaxPage(null, 'upload', 0)).toBe(1)
  })
})

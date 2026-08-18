import { describe, expect, it } from 'vite-plus/test'

describe('toolchain smoke test', () => {
  it('keeps the Vite+ test runner healthy', () => {
    expect(1 + 1).toBe(2)
  })
})

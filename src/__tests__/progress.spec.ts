import { describe, it, expect } from 'vite-plus/test'
import {
  calculateProgressPercent,
  calculateFloatPercent,
  truncateProgressFloat,
} from '@/utils/progress'

describe('progress utility module', () => {
  describe('calculateProgressPercent', () => {
    it('returns 0 for negative, zero or NaN values', () => {
      expect(calculateProgressPercent(0, 100)).toBe(0)
      expect(calculateProgressPercent(-10, 100)).toBe(0)
      expect(calculateProgressPercent(50, 0)).toBe(0)
      expect(calculateProgressPercent(50, -100)).toBe(0)
      expect(calculateProgressPercent(Number.NaN, 100)).toBe(0)
      expect(calculateProgressPercent(50, Number.NaN)).toBe(0)
    })

    it('calculates intermediate percentages accurately', () => {
      expect(calculateProgressPercent(25, 100)).toBe(25)
      expect(calculateProgressPercent(50, 100)).toBe(50)
      expect(calculateProgressPercent(44, 208)).toBe(21)
    })

    it('enforces non-terminal clamp: clamps 207/208 (99.52%) to 99% rather than 100%', () => {
      expect(calculateProgressPercent(207, 208)).toBe(99)
      expect(calculateProgressPercent(999, 1000)).toBe(99)
    })

    it('returns 100 only when current reaches or exceeds total', () => {
      expect(calculateProgressPercent(208, 208)).toBe(100)
      expect(calculateProgressPercent(210, 208)).toBe(100)
    })
  })

  describe('calculateFloatPercent', () => {
    it('returns 0 for non-positive or NaN values', () => {
      expect(calculateFloatPercent(0)).toBe(0)
      expect(calculateFloatPercent(-0.5)).toBe(0)
      expect(calculateFloatPercent(Number.NaN)).toBe(0)
    })

    it('clamps 0.999 to 99%', () => {
      expect(calculateFloatPercent(0.999)).toBe(99)
      expect(calculateFloatPercent(0.9952)).toBe(99)
    })

    it('returns 100 when float is 1 or greater', () => {
      expect(calculateFloatPercent(1)).toBe(100)
      expect(calculateFloatPercent(1.5)).toBe(100)
    })
  })

  describe('truncateProgressFloat', () => {
    it('truncates floating point numbers to default 4 decimals', () => {
      // 44 / 208 = 0.21153846153846154
      expect(truncateProgressFloat(44 / 208)).toBe(0.2115)
      // 207 / 208 = 0.9951923076923077
      expect(truncateProgressFloat(207 / 208)).toBe(0.9952)
    })

    it('safely handles 0, NaN and custom decimals', () => {
      expect(truncateProgressFloat(0)).toBe(0)
      expect(truncateProgressFloat(Number.NaN)).toBe(0)
      expect(truncateProgressFloat(0.123456, 2)).toBe(0.12)
    })
  })
})

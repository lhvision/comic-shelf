import { afterEach, describe, it, expect, vi } from 'vite-plus/test'
import { sumPrecise, sumBy, clamp, round, toFiniteNumber } from '@/utils/math'

describe('math utility module', () => {
  describe('sumPrecise', () => {
    afterEach(() => vi.unstubAllGlobals())

    it('uses native sumPrecise when available', () => {
      const nativeSum = vi.fn<(values: Iterable<number>) => number>(() => 0.6)
      vi.stubGlobal('Math', Object.create(Math, { sumPrecise: { value: nativeSum } }))
      const values = [0.1, 0.2, 0.3]

      expect(sumPrecise(values)).toBe(0.6)
      expect(nativeSum).toHaveBeenCalledWith(values)
    })

    it('falls back to ordinary addition when native sumPrecise is unavailable', () => {
      vi.stubGlobal('Math', Object.create(Math, { sumPrecise: { value: undefined } }))

      expect(sumPrecise([1024, 2048, 512])).toBe(3584)
      expect(sumPrecise([0.1, 0.2, 0.3])).toBe(0.6000000000000001)
    })

    it('accurately sums integer arrays', () => {
      expect(sumPrecise([1, 2, 3, 4, 5, 6])).toBe(21)
      expect(sumPrecise([])).toBe(0)
    })

    it('handles numeric arrays and special values', () => {
      expect(sumPrecise([10, 20, 30])).toBe(60)
      expect(Number.isNaN(sumPrecise([NaN, 1]))).toBe(true)
    })

    it('supports general non-array iterables (Set, Generator)', () => {
      const set = new Set([10, 20, 30])
      expect(sumPrecise(set)).toBe(60)

      function* gen() {
        yield 1
        yield 2
        yield 3
      }
      expect(sumPrecise(gen())).toBe(6)
    })

    it('throws TypeError for non-iterable inputs', () => {
      expect(() => sumPrecise(null as unknown as Iterable<number>)).toThrow(TypeError)
      expect(() => sumPrecise(123 as unknown as Iterable<number>)).toThrow(TypeError)
    })
  })

  describe('sumBy', () => {
    it('sums property values from objects with zero intermediate array allocation', () => {
      const list = [
        { name: 'A', pages: 10 },
        { name: 'B', pages: 25 },
        { name: 'C', pages: 15 },
      ]
      expect(sumBy(list, (item) => item.pages)).toBe(50)
    })

    it('handles empty and optional fields safely', () => {
      const list: Array<{ val?: number }> = [{ val: 5 }, {}, { val: 10 }]
      expect(sumBy(list, (item) => item.val ?? 0)).toBe(15)
      expect(sumBy([], (item: { val: number }) => item.val)).toBe(0)
      expect(sumBy(null, (item: { val: number }) => item.val)).toBe(0)
      expect(sumBy(undefined, (item: { val: number }) => item.val)).toBe(0)
    })
  })

  describe('clamp', () => {
    it('clamps values within bounds', () => {
      expect(clamp(5, 0, 10)).toBe(5)
      expect(clamp(-5, 0, 10)).toBe(0)
      expect(clamp(15, 0, 10)).toBe(10)
    })

    it('auto-corrects when min > max', () => {
      expect(clamp(5, 10, 0)).toBe(5)
      expect(clamp(-5, 10, 0)).toBe(0)
      expect(clamp(15, 10, 0)).toBe(10)
    })

    it('handles NaN and invalid inputs gracefully', () => {
      expect(clamp(Number.NaN, 0, 10)).toBe(0)
      expect(clamp(5, Number.NaN, 10)).toBe(5)
      expect(clamp(-5, Number.NaN, 10)).toBe(0)
    })
  })

  describe('round', () => {
    it('rounds to integer by default', () => {
      expect(round(4.4)).toBe(4)
      expect(round(4.6)).toBe(5)
      expect(round(4.5)).toBe(5)
    })

    it('rounds to specified decimal places with EPSILON accuracy', () => {
      expect(round(1.23456, 2)).toBe(1.23)
      expect(round(1.23556, 2)).toBe(1.24)
      expect(round(0.9951923, 4)).toBe(0.9952)
      // 1.005 * 100 is 100.49999999999999 in raw IEEE-754; EPSILON ensures correct 1.01
      expect(round(1.005, 2)).toBe(1.01)
      expect(round(-1.005, 2)).toBe(-1.01)
    })

    it('safely handles 0, NaN, and Infinities', () => {
      expect(round(0)).toBe(0)
      expect(round(Number.NaN)).toBe(0)
      expect(round(Number.POSITIVE_INFINITY)).toBe(0)
    })
  })

  describe('toFiniteNumber', () => {
    it('returns finite numbers directly', () => {
      expect(toFiniteNumber(100)).toBe(100)
      expect(toFiniteNumber(0)).toBe(0)
      expect(toFiniteNumber(-3.14)).toBe(-3.14)
    })

    it('returns fallback for non-numbers, NaN, or Infinities', () => {
      expect(toFiniteNumber('100', 50)).toBe(50)
      expect(toFiniteNumber(Number.NaN, 10)).toBe(10)
      expect(toFiniteNumber(Number.POSITIVE_INFINITY, 0)).toBe(0)
      expect(toFiniteNumber(undefined, 0)).toBe(0)
      expect(toFiniteNumber(null, 100)).toBe(100)
    })
  })
})

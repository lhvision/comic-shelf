import { describe, it, expect } from 'vite-plus/test'
import {
  isNumber,
  isFiniteNumber,
  isString,
  isArray,
  isBrowser,
  isCompletedComic,
  isInProgressComic,
  isLocalComic,
  isPicacgComic,
  isJmComic,
} from '@/utils/is'
import type { LibrarySummary } from '@/types'

describe('is utility module (Type Guards & Predicates)', () => {
  describe('Number Guards', () => {
    it('isNumber & isFiniteNumber', () => {
      expect(isNumber(100)).toBe(true)
      expect(isNumber(0)).toBe(true)
      expect(isNumber(Number.NaN)).toBe(false)
      expect(isNumber('100')).toBe(false)

      expect(isFiniteNumber(100)).toBe(true)
      expect(isFiniteNumber(Number.POSITIVE_INFINITY)).toBe(false)
      expect(isFiniteNumber(Number.NEGATIVE_INFINITY)).toBe(false)
      expect(isFiniteNumber(Number.NaN)).toBe(false)
    })
  })

  describe('String & Collection Guards', () => {
    it('isString', () => {
      expect(isString('')).toBe(true)
      expect(isString('hello')).toBe(true)
      expect(isString(123)).toBe(false)
    })

    it('isArray', () => {
      expect(isArray([])).toBe(true)
      expect(isArray([1, 2])).toBe(true)
      expect(isArray({})).toBe(false)
    })
  })

  describe('Environment & Network Predicates', () => {
    it('isBrowser', () => {
      expect(typeof isBrowser()).toBe('boolean')
    })
  })

  describe('Domain Predicates (Paper Room Status)', () => {
    const mockComic = (lastPage: number, pageCount: number): LibrarySummary =>
      ({
        source: 'jm',
        source_id: '123',
        display_id: '123',
        title: '测试漫画',
        page_count: pageCount,
        last_page: lastPage,
        cached_pages: pageCount,
        favorite: false,
      }) as unknown as LibrarySummary

    it('isCompletedComic', () => {
      expect(isCompletedComic(mockComic(20, 20))).toBe(true)
      expect(isCompletedComic(mockComic(25, 20))).toBe(true)
      expect(isCompletedComic(mockComic(10, 20))).toBe(false)
      expect(isCompletedComic(mockComic(0, 20))).toBe(false)
      expect(isCompletedComic(null)).toBe(false)
    })

    it('isInProgressComic', () => {
      expect(isInProgressComic(mockComic(10, 20))).toBe(true)
      expect(isInProgressComic(mockComic(20, 20))).toBe(false)
      expect(isInProgressComic(mockComic(0, 20))).toBe(false)
      expect(isInProgressComic(null)).toBe(false)
    })

    it('source predicates', () => {
      expect(isLocalComic('local')).toBe(true)
      expect(isLocalComic('jm')).toBe(false)
      expect(isPicacgComic('picacg')).toBe(true)
      expect(isPicacgComic('jm')).toBe(false)
      expect(isJmComic('jm')).toBe(true)
      expect(isJmComic('local')).toBe(false)
    })
  })
})

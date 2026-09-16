import { describe, it, expect } from 'vite-plus/test'
import {
  isDef,
  isNil,
  isBoolean,
  isFunction,
  isNumber,
  isFiniteNumber,
  isPositiveNumber,
  isNonNegativeNumber,
  isInteger,
  isString,
  isNonEmptyString,
  isArray,
  isNonEmptyArray,
  isPlainObject,
  isEmpty,
  isBrowser,
  isTouchDevice,
  isHttpUrl,
  isCompletedComic,
  isInProgressComic,
  isUnreadComic,
  isMultiChapterComic,
  isLocalComic,
  isPicacgComic,
  isJmComic,
} from '@/utils/is'
import type { LibrarySummary } from '@/types'

describe('is utility module (Type Guards & Predicates)', () => {
  describe('Value & Nil Guards', () => {
    it('isDef & isNil', () => {
      expect(isDef(0)).toBe(true)
      expect(isDef('')).toBe(true)
      expect(isDef(false)).toBe(true)
      expect(isDef(null)).toBe(false)
      expect(isDef(undefined)).toBe(false)

      expect(isNil(null)).toBe(true)
      expect(isNil(undefined)).toBe(true)
      expect(isNil(0)).toBe(false)
      expect(isNil('')).toBe(false)
    })

    it('isBoolean & isFunction', () => {
      expect(isBoolean(true)).toBe(true)
      expect(isBoolean(false)).toBe(true)
      expect(isBoolean('true')).toBe(false)

      expect(isFunction(() => {})).toBe(true)
      expect(isFunction(Math.max)).toBe(true)
      expect(isFunction({})).toBe(false)
    })
  })

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

    it('isPositiveNumber, isNonNegativeNumber, isInteger', () => {
      expect(isPositiveNumber(1)).toBe(true)
      expect(isPositiveNumber(0)).toBe(false)
      expect(isPositiveNumber(-1)).toBe(false)

      expect(isNonNegativeNumber(0)).toBe(true)
      expect(isNonNegativeNumber(10)).toBe(true)
      expect(isNonNegativeNumber(-0.1)).toBe(false)

      expect(isInteger(10)).toBe(true)
      expect(isInteger(0)).toBe(true)
      expect(isInteger(10.5)).toBe(false)
    })
  })

  describe('String Guards', () => {
    it('isString & isNonEmptyString', () => {
      expect(isString('')).toBe(true)
      expect(isString('hello')).toBe(true)
      expect(isString(123)).toBe(false)

      expect(isNonEmptyString('hello')).toBe(true)
      expect(isNonEmptyString('')).toBe(false)
      expect(isNonEmptyString('   ')).toBe(false)
      expect(isNonEmptyString(null)).toBe(false)
    })
  })

  describe('Array & Object Guards', () => {
    it('isArray & isNonEmptyArray', () => {
      expect(isArray([])).toBe(true)
      expect(isArray([1, 2])).toBe(true)
      expect(isArray({})).toBe(false)

      expect(isNonEmptyArray([1])).toBe(true)
      expect(isNonEmptyArray([])).toBe(false)
      expect(isNonEmptyArray(null)).toBe(false)
    })

    it('isPlainObject', () => {
      expect(isPlainObject({})).toBe(true)
      expect(isPlainObject({ a: 1 })).toBe(true)
      expect(isPlainObject([])).toBe(false)
      expect(isPlainObject(null)).toBe(false)
      expect(isPlainObject(new Date())).toBe(false)
      expect(isPlainObject(/abc/)).toBe(false)
      expect(isPlainObject('string')).toBe(false)
      expect(isPlainObject(123)).toBe(false)
    })

    it('isEmpty', () => {
      expect(isEmpty(null)).toBe(true)
      expect(isEmpty(undefined)).toBe(true)
      expect(isEmpty('')).toBe(true)
      expect(isEmpty('   ')).toBe(true)
      expect(isEmpty([])).toBe(true)
      expect(isEmpty({})).toBe(true)
      expect(isEmpty(new Set())).toBe(true)
      expect(isEmpty(new Map())).toBe(true)

      expect(isEmpty(0)).toBe(false)
      expect(isEmpty(false)).toBe(false)
      expect(isEmpty('a')).toBe(false)
      expect(isEmpty([1])).toBe(false)
      expect(isEmpty({ a: 1 })).toBe(false)
      expect(isEmpty(new Set([1]))).toBe(false)
      expect(isEmpty(new Date())).toBe(false)
    })
  })

  describe('Environment & Network Predicates', () => {
    it('isBrowser', () => {
      expect(typeof isBrowser()).toBe('boolean')
    })

    it('isTouchDevice', () => {
      expect(typeof isTouchDevice()).toBe('boolean')
    })

    it('isHttpUrl', () => {
      expect(isHttpUrl('https://example.com/api')).toBe(true)
      expect(isHttpUrl('http://localhost:8080')).toBe(true)
      expect(isHttpUrl('/api/library')).toBe(false)
      expect(isHttpUrl('javascript:void(0)')).toBe(false)
      expect(isHttpUrl(null)).toBe(false)
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

    it('isUnreadComic', () => {
      expect(isUnreadComic(mockComic(0, 20))).toBe(true)
      expect(isUnreadComic({ ...mockComic(0, 20), last_page: undefined })).toBe(true)
      expect(isUnreadComic(mockComic(5, 20))).toBe(false)
      expect(isUnreadComic(mockComic(20, 20))).toBe(false)
      expect(isUnreadComic(null)).toBe(false)
    })

    it('isMultiChapterComic', () => {
      expect(isMultiChapterComic({ chapters: [{ id: '1' }, { id: '2' }] })).toBe(true)
      expect(isMultiChapterComic({ chapters: [{ id: '1' }] })).toBe(false)
      expect(isMultiChapterComic({ chapters: [] })).toBe(false)
      expect(isMultiChapterComic({})).toBe(false)
      expect(isMultiChapterComic(null)).toBe(false)
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

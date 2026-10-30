import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { nextTick } from 'vue'
import { useReadingSession } from '@/composables/useReadingSession'
import { useAuth } from '@/composables/useAuth'
import type { Router } from 'vue-router'

describe('useReadingSession', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('records an active reading session when not completed', () => {
    const { session, recordSession } = useReadingSession()

    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 12,
      totalPages: 30,
    })

    expect(session.value).not.toBeNull()
    expect(session.value?.source).toBe('jm')
    expect(session.value?.sourceId).toBe('12345')
    expect(session.value?.page).toBe(12)
    expect(session.value?.totalPages).toBe(30)
    expect(session.value?.active).toBe(true)
  })

  it('marks active as false when comic is read to completion', () => {
    const { session, recordSession } = useReadingSession()

    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 30,
      totalPages: 30,
    })

    expect(session.value?.active).toBe(false)
  })

  it('deactivates active session when user leaves normally', () => {
    const { session, recordSession, deactivateSession } = useReadingSession()

    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 15,
      totalPages: 40,
    })
    expect(session.value?.active).toBe(true)

    deactivateSession()
    expect(session.value?.active).toBe(false)
    // Page progress is preserved
    expect(session.value?.page).toBe(15)
  })

  it('does not resume session when not in standalone mode', () => {
    const { recordSession, tryResumeSession } = useReadingSession()
    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 10,
      totalPages: 30,
    })

    const replaceSpy = vi.fn<() => Promise<void>>()
    const router = { replace: replaceSpy } as unknown as Router
    const toastSpy = vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => void>()

    const resumed = tryResumeSession(router, toastSpy)
    expect(resumed).toBe(false)
    expect(replaceSpy).not.toHaveBeenCalled()
    expect(toastSpy).not.toHaveBeenCalled()
  })

  it('resumes session in standalone mode with valid active session', () => {
    // Mock standalone mode
    window.matchMedia = vi
      .fn<(query: string) => MediaQueryList>()
      .mockImplementation((query: string) => ({
        matches: query === '(display-mode: standalone)',
        media: query,
        onchange: null,
        addListener: vi.fn<() => void>(),
        removeListener: vi.fn<() => void>(),
        addEventListener: vi.fn<() => void>(),
        removeEventListener: vi.fn<() => void>(),
        dispatchEvent: vi.fn<() => boolean>(),
      }))

    const { recordSession, tryResumeSession } = useReadingSession()
    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 8,
      totalPages: 24,
    })

    const replaceSpy = vi.fn<() => Promise<void>>()
    const router = { replace: replaceSpy } as unknown as Router
    const toastSpy = vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => void>()

    const resumed = tryResumeSession(router, toastSpy)
    expect(resumed).toBe(true)
    expect(replaceSpy).toHaveBeenCalledWith('/comic/jm/12345/read/8')
    expect(toastSpy).toHaveBeenCalledWith('已为您恢复上次在读：第 8 页', 'info')
  })

  it('refuses to resume if resumeOnLaunch is toggled off', () => {
    window.matchMedia = vi
      .fn<(query: string) => MediaQueryList>()
      .mockImplementation((query: string) => ({
        matches: query === '(display-mode: standalone)',
        media: query,
        onchange: null,
        addListener: vi.fn<() => void>(),
        removeListener: vi.fn<() => void>(),
        addEventListener: vi.fn<() => void>(),
        removeEventListener: vi.fn<() => void>(),
        dispatchEvent: vi.fn<() => boolean>(),
      }))

    const { recordSession, resumeOnLaunch, tryResumeSession } = useReadingSession()
    resumeOnLaunch.value = false

    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 8,
      totalPages: 24,
    })

    const replaceSpy = vi.fn<() => Promise<void>>()
    const router = { replace: replaceSpy } as unknown as Router
    const toastSpy = vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => void>()

    const resumed = tryResumeSession(router, toastSpy)
    expect(resumed).toBe(false)
    expect(replaceSpy).not.toHaveBeenCalled()
  })

  it('isolates reading sessions across user identities', async () => {
    const { recordSession, session, tryResumeSession } = useReadingSession()
    recordSession({
      source: 'jm',
      sourceId: 'curator_secret',
      page: 10,
      totalPages: 50,
    })
    expect(session.value?.sourceId).toBe('curator_secret')
    expect(session.value?.userId).toBe('default')

    await nextTick()

    // Session contains userId
    const raw = localStorage.getItem('comic-shelf:active-reading-session:v1')
    expect(raw).toContain('curator_secret')
    expect(raw).toContain('default')

    // If another user (e.g. guest) is logged in, tryResumeSession rejects cross-user resume
    window.matchMedia = vi
      .fn<(query: string) => MediaQueryList>()
      .mockImplementation((query: string) => ({
        matches: query === '(display-mode: standalone)',
        media: query,
        onchange: null,
        addListener: vi.fn<() => void>(),
        removeListener: vi.fn<() => void>(),
        addEventListener: vi.fn<() => void>(),
        removeEventListener: vi.fn<() => void>(),
        dispatchEvent: vi.fn<() => boolean>(),
      }))

    // Simulate session owned by a different user
    if (session.value) {
      session.value.userId = 'guest_different_account'
    }

    const replaceSpy = vi.fn<() => Promise<void>>()
    const router = { replace: replaceSpy } as unknown as Router
    const toastSpy = vi.fn<(msg: string, tone?: 'info' | 'error' | 'success') => void>()

    const resumed = tryResumeSession(router, toastSpy)
    expect(resumed).toBe(false)
    expect(replaceSpy).not.toHaveBeenCalled()

    // Even if legacy session has missing userId, it defaults to 'default'
    if (session.value) {
      delete session.value.userId
    }
    // Now if userId of auth profile is different (e.g. curator), it still rejects
    const { userId } = useAuth()
    userId.value = 'curator_admin'
    expect(tryResumeSession(router, toastSpy)).toBe(false)
    userId.value = ''
  })

  it('sanitizes NaN and non-finite page inputs defensively', () => {
    const { session, recordSession } = useReadingSession()
    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: NaN,
      totalPages: 20,
    })
    expect(session.value?.page).toBe(1)

    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: -5,
      totalPages: 20,
    })
    expect(session.value?.page).toBe(1)

    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 12.8,
      totalPages: 20,
    })
    expect(session.value?.page).toBe(12)
  })

  it('clears active reading session on clearSession', () => {
    const { session, recordSession, clearSession } = useReadingSession()
    recordSession({
      source: 'jm',
      sourceId: '12345',
      page: 5,
      totalPages: 20,
    })
    expect(session.value).not.toBeNull()

    clearSession()
    expect(session.value).toBeNull()
  })
})

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

  it('resumes session on launch with valid active session', () => {
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
    expect(resumed).toBe(true)
    expect(replaceSpy).toHaveBeenCalledWith('/comic/jm/12345/read/10')
    expect(toastSpy).toHaveBeenCalledWith('已为您恢复上次在读：第 10 页', 'info')
  })

  it('refuses to resume if resumeOnLaunch is toggled off', () => {
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
    expect(session.value?.userId).toBe('curator')

    await nextTick()

    // Session contains userId
    const raw = localStorage.getItem('comic-shelf:active-reading-session:v1')
    expect(raw).toContain('curator_secret')
    expect(raw).toContain('curator')

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

    // Now if userId of auth profile is different (e.g. curator_admin), it still rejects
    const { userId } = useAuth()
    userId.value = 'guest:pass_1'
    expect(tryResumeSession(router, toastSpy)).toBe(false)
    userId.value = ''
  })

  it('preserves reading session during initial auth hydration, but clears on logout or account switch', async () => {
    const { userId } = useAuth()
    userId.value = '' // initial unhydrated state

    const { recordSession, session } = useReadingSession()
    recordSession({
      source: 'jm',
      sourceId: 'shelf_book',
      page: 5,
      totalPages: 20,
    })
    expect(session.value).not.toBeNull()

    // 1. Initial auth hydration from "" to "curator" MUST NOT wipe session
    userId.value = 'curator'
    await nextTick()
    expect(session.value).not.toBeNull()
    expect(session.value?.sourceId).toBe('shelf_book')

    // 2. Account switch from "curator" to "guest:pass_abc" MUST wipe session
    userId.value = 'guest:pass_abc'
    await nextTick()
    expect(session.value).toBeNull()

    // 3. New session for guest
    recordSession({
      source: 'jm',
      sourceId: 'guest_book',
      page: 2,
      totalPages: 10,
    })
    expect(session.value?.sourceId).toBe('guest_book')

    // 4. Explicit logout ("guest:pass_abc" to "") MUST wipe session
    userId.value = ''
    await nextTick()
    expect(session.value).toBeNull()
  })

  it('refuses to resume session if auth is required and user is unauthenticated', () => {
    const { authRequired, authenticated } = useAuth()
    authRequired.value = true
    authenticated.value = false

    const { recordSession, tryResumeSession } = useReadingSession()
    recordSession({
      source: 'jm',
      sourceId: 'secret_book',
      page: 10,
      totalPages: 30,
    })

    const replaceSpy = vi.fn<() => Promise<void>>()
    const router = { replace: replaceSpy } as unknown as Router
    const toastSpy = vi.fn<() => void>()

    expect(tryResumeSession(router, toastSpy)).toBe(false)
    expect(replaceSpy).not.toHaveBeenCalled()

    authRequired.value = false
    authenticated.value = true
  })

  it('strictly enforces single-book sandbox boundary during resume', () => {
    const { userId, authenticated } = useAuth()
    authenticated.value = true
    userId.value = 'direct:local:book_allowed'

    const { recordSession, session, tryResumeSession } = useReadingSession()

    // 1. Session for a DIFFERENT comic must be rejected
    recordSession({
      source: 'local',
      sourceId: 'book_forbidden',
      page: 5,
      totalPages: 20,
    })
    // Simulate user identity on session
    if (session.value) {
      session.value.userId = 'direct:local:book_allowed'
    }

    const replaceSpy = vi.fn<() => Promise<void>>()
    const router = { replace: replaceSpy } as unknown as Router
    const toastSpy = vi.fn<() => void>()

    expect(tryResumeSession(router, toastSpy)).toBe(false)
    expect(replaceSpy).not.toHaveBeenCalled()

    // 2. Session for the ALLOWED comic succeeds
    recordSession({
      source: 'local',
      sourceId: 'book_allowed',
      page: 5,
      totalPages: 20,
    })
    if (session.value) {
      session.value.userId = 'direct:local:book_allowed'
    }

    expect(tryResumeSession(router, toastSpy)).toBe(true)
    expect(replaceSpy).toHaveBeenCalledWith('/comic/local/book_allowed/read/5')

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

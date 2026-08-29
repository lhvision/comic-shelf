import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { useAuth } from '@/composables/useAuth'
import { api, ApiError, getStoredToken, setStoredToken } from '@/api/client'

describe('useAuth', () => {
  beforeEach(() => {
    setStoredToken('')
    vi.restoreAllMocks()
  })

  it('checks auth status when auth is disabled', async () => {
    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: false,
      authenticated: true,
      can_write: true,
      role: 'admin',
    })

    const { authRequired, authenticated, canWrite, isGuest, modalVisible, checkStatus } = useAuth()
    await checkStatus()

    expect(authRequired.value).toBe(false)
    expect(authenticated.value).toBe(true)
    expect(canWrite.value).toBe(true)
    expect(isGuest.value).toBe(false)
    expect(modalVisible.value).toBe(false)
  })

  it('opens modal when auth is required and not authenticated', async () => {
    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: true,
      authenticated: false,
      can_write: false,
      role: 'unauthorized',
    })

    const { authRequired, authenticated, canWrite, isGuest, modalVisible, checkStatus } = useAuth()
    await checkStatus()

    expect(authRequired.value).toBe(true)
    expect(authenticated.value).toBe(false)
    expect(canWrite.value).toBe(false)
    expect(isGuest.value).toBe(false)
    expect(modalVisible.value).toBe(true)
  })

  it('handles login flow as curator', async () => {
    vi.spyOn(api, 'login').mockResolvedValueOnce({
      ok: true,
      token: 'curator-pass-123',
      role: 'admin',
    })

    const { authenticated, canWrite, isGuest, modalVisible, login } = useAuth()
    const success = await login('curator-pass-123')

    expect(success).toBe(true)
    expect(authenticated.value).toBe(true)
    expect(canWrite.value).toBe(true)
    expect(isGuest.value).toBe(false)
    expect(modalVisible.value).toBe(false)
    expect(getStoredToken()).toBe('curator-pass-123')
  })

  it('handles login flow as guest', async () => {
    vi.spyOn(api, 'login').mockResolvedValueOnce({
      ok: true,
      token: 'guest-pass-456',
      role: 'guest',
    })

    const { authenticated, canWrite, isGuest, modalVisible, login } = useAuth()
    const success = await login('guest-pass-456')

    expect(success).toBe(true)
    expect(authenticated.value).toBe(true)
    expect(canWrite.value).toBe(false)
    expect(isGuest.value).toBe(true)
    expect(modalVisible.value).toBe(false)
    expect(getStoredToken()).toBe('guest-pass-456')
  })

  it('handles logout flow and clears stored token', async () => {
    setStoredToken('test-pass-123')
    vi.spyOn(api, 'logout').mockResolvedValueOnce({ ok: true })

    const { authenticated, canWrite, logout } = useAuth()
    await logout()

    expect(authenticated.value).toBe(false)
    expect(canWrite.value).toBe(false)
    expect(getStoredToken()).toBe('')
  })

  it('restores curator privileges when status returns guest but valid curator token exists', async () => {
    setStoredToken('curator-secret-777')
    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: true,
      authenticated: true,
      can_write: false,
      role: 'guest',
    })
    vi.spyOn(api, 'login').mockResolvedValueOnce({
      ok: true,
      token: 'curator-secret-777',
      role: 'admin',
    })

    const { authenticated, canWrite, isGuest, role, checkStatus } = useAuth()
    await checkStatus()

    expect(authenticated.value).toBe(true)
    expect(canWrite.value).toBe(true)
    expect(isGuest.value).toBe(false)
    expect(role.value).toBe('admin')
    expect(getStoredToken()).toBe('curator-secret-777')
  })

  it('preserves stored token on transient network failure during checkStatus', async () => {
    setStoredToken('curator-secret-888')
    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: true,
      authenticated: false,
      can_write: false,
      role: 'unauthorized',
    })
    vi.spyOn(api, 'login').mockRejectedValueOnce(new TypeError('Failed to fetch (offline)'))

    const { checkStatus } = useAuth()
    await checkStatus()

    // Token must NOT be wiped on network errors
    expect(getStoredToken()).toBe('curator-secret-888')
  })

  it('clears stored token when server rejects credentials with ApiError 401', async () => {
    setStoredToken('invalid-secret-999')
    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: true,
      authenticated: false,
      can_write: false,
      role: 'unauthorized',
    })
    vi.spyOn(api, 'login').mockRejectedValueOnce(new ApiError(401, '通行口令错误，请重试'))

    const { checkStatus } = useAuth()
    await checkStatus()

    expect(getStoredToken()).toBe('')
  })

  it('preserves stored token on gateway/server error with ApiError 502', async () => {
    setStoredToken('valid-secret-999')
    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: true,
      authenticated: false,
      can_write: false,
      role: 'unauthorized',
    })
    vi.spyOn(api, 'login').mockRejectedValueOnce(new ApiError(502, 'Bad Gateway'))

    const { checkStatus } = useAuth()
    await checkStatus()

    expect(getStoredToken()).toBe('valid-secret-999')
  })

  it('automatically logs in when ?token=... is present in URL search', async () => {
    const origLocation = window.location
    const mockLocation = new URL('http://localhost:5173/?token=share-token-123')
    Object.defineProperty(window, 'location', {
      value: mockLocation,
      writable: true,
      configurable: true,
    })

    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: true,
      authenticated: false,
      can_write: false,
      role: 'unauthorized',
    })
    vi.spyOn(api, 'login').mockResolvedValueOnce({
      ok: true,
      token: 'share-token-123',
      role: 'guest',
      username: 'AliceFriend',
      user_id: 'guest:5',
    })

    const { authenticated, isGuest, username, userId, modalVisible, checkStatus } = useAuth()
    const ok = await checkStatus()

    expect(ok).toBe(true)
    expect(authenticated.value).toBe(true)
    expect(isGuest.value).toBe(true)
    expect(username.value).toBe('AliceFriend')
    expect(userId.value).toBe('guest:5')
    expect(modalVisible.value).toBe(false)
    expect(getStoredToken()).toBe('share-token-123')

    Object.defineProperty(window, 'location', {
      value: origLocation,
      writable: true,
      configurable: true,
    })
  })
})

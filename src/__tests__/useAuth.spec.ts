import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { useAuth } from '@/composables/useAuth'
import { api, getStoredToken, setStoredToken } from '@/api/client'

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
})

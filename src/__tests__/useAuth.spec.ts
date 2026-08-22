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
    })

    const { authRequired, authenticated, modalVisible, checkStatus } = useAuth()
    await checkStatus()

    expect(authRequired.value).toBe(false)
    expect(authenticated.value).toBe(true)
    expect(modalVisible.value).toBe(false)
  })

  it('opens modal when auth is required and not authenticated', async () => {
    vi.spyOn(api, 'authStatus').mockResolvedValueOnce({
      auth_required: true,
      authenticated: false,
    })

    const { authRequired, authenticated, modalVisible, checkStatus } = useAuth()
    await checkStatus()

    expect(authRequired.value).toBe(true)
    expect(authenticated.value).toBe(false)
    expect(modalVisible.value).toBe(true)
  })

  it('handles login flow successfully', async () => {
    vi.spyOn(api, 'login').mockResolvedValueOnce({
      ok: true,
      token: 'test-pass-123',
    })

    const { authenticated, modalVisible, login } = useAuth()
    const success = await login('test-pass-123')

    expect(success).toBe(true)
    expect(authenticated.value).toBe(true)
    expect(modalVisible.value).toBe(false)
    expect(getStoredToken()).toBe('test-pass-123')
  })

  it('handles logout flow and clears stored token', async () => {
    setStoredToken('test-pass-123')
    vi.spyOn(api, 'logout').mockResolvedValueOnce({ ok: true })

    const { authenticated, logout } = useAuth()
    await logout()

    expect(authenticated.value).toBe(false)
    expect(getStoredToken()).toBe('')
  })
})

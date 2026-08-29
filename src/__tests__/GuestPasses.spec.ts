import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { useGuestPasses } from '@/composables/useGuestPasses'
import { api } from '@/api/client'
import type { GuestPass } from '@/types'

vi.mock('@/api/client', () => ({
  api: {
    getCuratorPasses: vi.fn<() => Promise<GuestPass[]>>(),
    createCuratorPass: vi.fn<() => Promise<GuestPass>>(),
    updateCuratorPass: vi.fn<() => Promise<GuestPass>>(),
    deleteCuratorPass: vi.fn<() => Promise<{ ok: boolean }>>(),
  },
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ toast: vi.fn<(msg: string, type?: string) => void>() }),
}))

describe('useGuestPasses', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches passes and updates state', async () => {
    const mockPasses = [
      {
        id: 1,
        username: 'FriendA',
        token: 'token12345678901234567890123456',
        expires_at: 1800000000,
        is_active: true,
        is_expired: false,
        created_at: 1700000000,
        updated_at: 1700000000,
      },
    ]
    vi.mocked(api.getCuratorPasses).mockResolvedValueOnce(mockPasses)

    const { passes, fetchPasses, loading } = useGuestPasses()
    expect(loading.value).toBe(false)
    await fetchPasses()
    expect(passes.value).toEqual(mockPasses)
  })

  it('creates pass and prepends to list', async () => {
    const newPass = {
      id: 2,
      username: 'FriendB',
      token: 'token22222222222222222222222222',
      expires_at: null,
      is_active: true,
      is_expired: false,
      created_at: 1700000000,
      updated_at: 1700000000,
    }
    vi.mocked(api.createCuratorPass).mockResolvedValueOnce(newPass)

    const { createPass, passes } = useGuestPasses()
    const created = await createPass({ username: 'FriendB', expires_days: null })
    expect(created).toEqual(newPass)
    expect(passes.value[0]).toEqual(newPass)
  })

  it('renews pass and updates in list', async () => {
    const updated = {
      id: 1,
      username: 'FriendA',
      token: 'token12345678901234567890123456',
      expires_at: 1900000000,
      is_active: true,
      is_expired: false,
      created_at: 1700000000,
      updated_at: 1700000100,
    }
    vi.mocked(api.updateCuratorPass).mockResolvedValueOnce(updated)

    const { renewPass, passes } = useGuestPasses()
    passes.value = [{ ...updated, expires_at: 1800000000 }]
    await renewPass(1, 30)
    expect(passes.value[0]?.expires_at).toBe(1900000000)
  })

  it('deletes pass and removes from list', async () => {
    vi.mocked(api.deleteCuratorPass).mockResolvedValueOnce({ ok: true })

    const { removePass, passes } = useGuestPasses()
    passes.value = [
      {
        id: 99,
        username: 'RemoveMe',
        token: 'token99999999999999999999999999',
        expires_at: null,
        is_active: true,
        is_expired: false,
        created_at: 1700000000,
        updated_at: 1700000000,
      },
    ]
    await removePass(99)
    expect(passes.value).toHaveLength(0)
  })
})

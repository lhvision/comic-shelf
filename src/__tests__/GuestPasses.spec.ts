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
    deleteCuratorPassDevice: vi.fn<() => Promise<{ ok: boolean }>>(),
  },
}))

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

describe('useGuestPasses', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches passes and updates state', async () => {
    const mockPasses: GuestPass[] = [
      {
        id: 1,
        username: 'FriendA',
        token: 'token12345678901234567890123456',
        expires_at: 1800000000,
        is_active: true,
        is_expired: false,
        max_devices: 2,
        device_count: 0,
        devices: [],
        first_used_at: null,
        last_used_at: null,
        activation_status: 'pending',
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
    const newPass: GuestPass = {
      id: 2,
      username: 'FriendB',
      token: 'token22222222222222222222222222',
      expires_at: null,
      is_active: true,
      is_expired: false,
      max_devices: 2,
      device_count: 0,
      devices: [],
      first_used_at: null,
      last_used_at: null,
      activation_status: 'pending',
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
    const updated: GuestPass = {
      id: 1,
      username: 'FriendA',
      token: 'token12345678901234567890123456',
      expires_at: 1900000000,
      is_active: true,
      is_expired: false,
      max_devices: 2,
      device_count: 0,
      devices: [],
      first_used_at: null,
      last_used_at: null,
      activation_status: 'pending',
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
        max_devices: 2,
        device_count: 0,
        devices: [],
        first_used_at: null,
        last_used_at: null,
        activation_status: 'pending',
        created_at: 1700000000,
        updated_at: 1700000000,
      },
    ]
    await removePass(99)
    expect(passes.value).toHaveLength(0)
  })

  it('removes device and updates pass status in list', async () => {
    vi.mocked(api.deleteCuratorPassDevice).mockResolvedValueOnce({ ok: true })

    const { removeDevice, passes } = useGuestPasses()
    passes.value = [
      {
        id: 10,
        username: 'UserMulti',
        token: 'tokenmulti12345678901234567890',
        expires_at: null,
        is_active: true,
        is_expired: false,
        max_devices: 2,
        device_count: 1,
        devices: [
          {
            id: 101,
            pass_id: 10,
            device_token: 'devtoken1',
            device_name: 'iPhone · Safari',
            user_agent: 'iPhone',
            last_ip: '1.2.3.4',
            created_at: 1700000000,
            last_active_at: 1700000000,
          },
        ],
        first_used_at: 1700000000,
        last_used_at: 1700000000,
        activation_status: 'active',
        created_at: 1700000000,
        updated_at: 1700000000,
      },
    ]

    const ok = await removeDevice(10, 101)
    expect(ok).toBe(true)
    expect(passes.value[0]?.device_count).toBe(0)
    expect(passes.value[0]?.activation_status).toBe('pending')
    expect(passes.value[0]?.devices).toHaveLength(0)
  })

  it('copyToken warns when device_count > 0 and succeeds cleanly when 0', async () => {
    const { copyToken } = useGuestPasses()

    // Pass with 1 device
    const activePass: GuestPass = {
      id: 20,
      username: 'UsedUser',
      token: 'tokentokentoken',
      expires_at: null,
      is_active: true,
      is_expired: false,
      max_devices: 2,
      device_count: 1,
      devices: [],
      first_used_at: 1700000000,
      last_used_at: 1700000000,
      activation_status: 'active',
      created_at: 1700000000,
      updated_at: 1700000000,
    }
    await copyToken(activePass)
    expect(mockToast).toHaveBeenCalledWith(expect.stringContaining('谨防设备互挤'), 'info')

    mockToast.mockClear()

    // Pass with 0 devices
    const freshPass: GuestPass = {
      ...activePass,
      device_count: 0,
      activation_status: 'pending',
    }
    await copyToken(freshPass)
    expect(mockToast).toHaveBeenCalledWith(expect.stringContaining('可安心发放给新朋友'), 'success')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import GuestDeviceList from '@/components/curator/guest/GuestDeviceList.vue'
import GuestCard from '@/components/curator/guest/GuestCard.vue'
import GuestSuccessVoucher from '@/components/curator/guest/GuestSuccessVoucher.vue'
import GuestRosterTab from '@/components/curator/guest/GuestRosterTab.vue'
import GuestIssueTab from '@/components/curator/guest/GuestIssueTab.vue'
import type { GuestPass } from '@/types'

const mockToast = vi.fn<(msg: string, type?: string) => void>()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

const mockCopy = vi.fn<(text: string) => Promise<void>>()
vi.mock('@vueuse/core', async () => {
  const actual = await vi.importActual('@vueuse/core')
  return {
    ...actual,
    useClipboard: () => ({ copy: mockCopy }),
  }
})

describe('Guest Modal Components', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const samplePass: GuestPass = {
    id: 1,
    username: 'TestUser',
    token: 'token12345678901234567890',
    expires_at: 1800000000,
    is_active: true,
    is_expired: false,
    is_claimed: true,
    max_devices: 2,
    device_count: 1,
    devices: [
      {
        id: 101,
        pass_id: 1,
        device_token: 'devtoken1',
        device_name: 'Chrome on MacOS',
        user_agent: 'Chrome',
        last_ip: '192.168.1.5',
        created_at: 1700000000,
        last_active_at: 1700000000,
      },
    ],
    activation_status: 'active',
    created_at: 1700000000,
    updated_at: 1700000000,
  }

  describe('GuestDeviceList', () => {
    it('renders device chips correctly', () => {
      const wrapper = mount(GuestDeviceList, {
        props: {
          devices: samplePass.devices,
          passId: samplePass.id,
          operatingId: null,
        },
      })
      expect(wrapper.text()).toContain('Chrome on MacOS')
      expect(wrapper.text()).toContain('192.168.1.5')
    })

    it('handles kick confirmation interaction', async () => {
      const wrapper = mount(GuestDeviceList, {
        props: {
          devices: samplePass.devices,
          passId: samplePass.id,
          operatingId: null,
        },
      })
      const kickBtn = wrapper.find('.device-kick-btn')
      await kickBtn.trigger('click')
      expect(wrapper.text()).toContain('下线？')

      const confirmBtn = wrapper.find('.device-kick-action.confirm-yes')
      await confirmBtn.trigger('click')
      expect(wrapper.emitted('removeDevice')).toBeTruthy()
      expect(wrapper.emitted('removeDevice')![0]).toEqual([1, 101])
    })
  })

  describe('GuestCard', () => {
    it('renders pass username and status seal', () => {
      const wrapper = mount(GuestCard, {
        props: {
          item: samplePass,
        },
      })
      expect(wrapper.find('.pass-name').text()).toBe('TestUser')
      expect(wrapper.find('.status-seal').text()).toContain('活跃 · 1/2台')
    })
  })

  describe('GuestSuccessVoucher', () => {
    it('renders voucher details and triggers navigation emits', async () => {
      const wrapper = mount(GuestSuccessVoucher, {
        props: {
          pass: samplePass,
        },
      })
      expect(wrapper.text()).toContain('通行凭据已印发')
      expect(wrapper.text()).toContain('TestUser')

      const navBtns = wrapper.findAllComponents({ name: 'AppButton' })
      expect(navBtns.length).toBe(2)
      await navBtns[0]!.trigger('click')
      expect(wrapper.emitted('issueNext')).toBeTruthy()
      await navBtns[1]!.trigger('click')
      expect(wrapper.emitted('viewRoster')).toBeTruthy()
    })
  })

  describe('GuestRosterTab', () => {
    it('renders and filters passes according to search query', async () => {
      const wrapper = mount(GuestRosterTab, {
        props: {
          passes: [
            samplePass,
            { ...samplePass, id: 2, username: 'OtherPerson' },
            { ...samplePass, id: 3, username: 'ThirdGuy' },
          ],
          loading: false,
          fetchError: null,
        },
      })
      expect(wrapper.findAllComponents(GuestCard).length).toBe(3)

      const searchInput = wrapper.find('.roster-search-input')
      expect(searchInput.exists()).toBe(true)
      await searchInput.setValue('nonexistent')
      expect(wrapper.findAllComponents(GuestCard).length).toBe(0)
    })
  })

  describe('GuestIssueTab', () => {
    it('renders form input and handles submit', async () => {
      const wrapper = mount(GuestIssueTab, {
        props: {
          justCreatedPass: null,
        },
      })
      const input = wrapper.find('#modal-guest-name-input')
      expect(input.exists()).toBe(true)
      await input.setValue('NewVisitor')
      const submitBtn = wrapper.findComponent({ name: 'AppButton' })
      expect(submitBtn.exists()).toBe(true)
    })
  })
})

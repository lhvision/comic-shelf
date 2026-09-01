import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderSettingsPanel from '@/components/reader/ReaderSettingsPanel.vue'
import ReaderHud from '@/components/reader/ReaderHud.vue'
import { useReaderSettings, DEFAULT_SETTINGS } from '@/composables/useReaderSettings'

describe('Reader AutoTurn Custom Seconds and Paused Icon', () => {
  beforeEach(() => {
    const { settings } = useReaderSettings()
    Object.assign(settings, DEFAULT_SETTINGS)
  })

  it('allows selecting presets and entering custom seconds in ReaderSettingsPanel', async () => {
    const { settings } = useReaderSettings()
    settings.autoTurn = true
    settings.autoTurnInterval = 10

    const wrapper = mount(ReaderSettingsPanel, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    // Preset buttons and custom chip button
    const presetButtons = wrapper.findAll('.auto-turn-options button')
    expect(presetButtons.length).toBe(5) // 4 presets (5, 10, 15, 30) + 1 custom button
    expect(wrapper.find('.custom-chip-btn').text()).toBe('自定义…')

    // Click custom button to activate input
    await wrapper.find('.custom-chip-btn').trigger('click')

    const input = wrapper.find('.custom-interval-input')
    expect(input.exists()).toBe(true)

    // Set custom value to 25 seconds
    await input.setValue(25)
    await input.trigger('blur')

    expect(settings.autoTurnInterval).toBe(25)
    expect(wrapper.text()).toContain('每 25 秒切到下一屏')

    // Click preset 15秒 to switch back
    const btn15 = wrapper.findAll('.auto-turn-options button')[2]
    expect(btn15?.text()).toBe('15 秒')
    await btn15?.trigger('click')
    expect(settings.autoTurnInterval).toBe(15)
    expect(wrapper.find('.custom-chip-btn').exists()).toBe(true)
  })

  it('renders countdown number when autoTurn is active and pause icon when paused in ReaderHud', async () => {
    const wrapper = mount(ReaderHud, {
      props: {
        autoTurn: true,
        atLastGroup: false,
        autoTurnPaused: false,
        settingsOpen: false,
        autoTurnRemaining: 8,
        currentGroupLabel: '1',
        total: 20,
        prevSymbol: '←',
        nextSymbol: '→',
        canPrev: false,
        canNext: true,
        hidden: false,
      },
    })

    // Running state: displays remaining number 8
    expect(wrapper.find('.auto-turn-count').text()).toBe('8')
    expect(wrapper.find('.app-icon--pause').exists()).toBe(false)
    expect(wrapper.find('.auto-turn-countdown').attributes('data-paused')).toBe('false')

    // Paused state: displays pause icon
    await wrapper.setProps({
      autoTurnPaused: true,
    } as Record<string, unknown>)

    expect(wrapper.find('.auto-turn-count').exists()).toBe(false)
    expect(wrapper.find('.app-icon--pause').exists()).toBe(true)
    expect(wrapper.find('.auto-turn-countdown').attributes('data-paused')).toBe('true')
  })

  it('emits toggleAutoTurnPause when countdown button is clicked', async () => {
    const wrapper = mount(ReaderHud, {
      props: {
        autoTurn: true,
        atLastGroup: false,
        autoTurnPaused: false,
        settingsOpen: false,
        autoTurnRemaining: 8,
        currentGroupLabel: '1',
        total: 20,
        prevSymbol: '←',
        nextSymbol: '→',
        canPrev: false,
        canNext: true,
        hidden: false,
      },
    })

    await wrapper.find('.auto-turn-countdown').trigger('click')
    expect(wrapper.emitted('toggleAutoTurnPause')).toBeTruthy()
  })
})

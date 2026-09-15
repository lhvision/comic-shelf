import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import ReaderSettingsPanel from '@/components/reader/ReaderSettingsPanel.vue'
import ReaderHud from '@/components/reader/ReaderHud.vue'
import {
  useReaderSettings,
  DEFAULT_SETTINGS,
  type ReaderSettings,
} from '@/composables/useReaderSettings'

describe('Reader AutoTurn Custom Seconds and Paused Icon', () => {
  beforeEach(() => {
    const { settings } = useReaderSettings()
    Object.assign(settings, DEFAULT_SETTINGS)
  })

  it('allows selecting presets and entering custom seconds in ReaderSettingsPanel for paged mode', async () => {
    const { settings } = useReaderSettings()
    settings.mode = 'vertical-paged'
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

  it('does not display autoTurn settings group in vertical-continuous mode in ReaderSettingsPanel', async () => {
    const { settings } = useReaderSettings()
    settings.mode = 'vertical-continuous'
    settings.autoTurn = true

    const wrapper = mount(ReaderSettingsPanel, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    // AutoTurn settings group should be hidden for vertical-continuous mode
    expect(wrapper.find('.auto-turn-options').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('切到下一屏')
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
        prevIcon: 'arrow-left',
        nextIcon: 'arrow-right',
        canPrev: false,
        canNext: true,
        hidden: false,
      },
    })

    // Running state: displays remaining number 8
    expect(wrapper.find('.auto-turn-count').text()).toBe('8')
    expect(wrapper.find('.app-icon--pause').exists()).toBe(false)
    expect(wrapper.find('.auto-turn-countdown').attributes('data-paused')).toBe('false')

    // Paused state: displays play icon to resume
    await wrapper.setProps({
      autoTurnPaused: true,
    } as Record<string, unknown>)

    expect(wrapper.find('.auto-turn-count').exists()).toBe(false)
    expect(wrapper.find('.app-icon--play').exists()).toBe(true)
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
        prevIcon: 'arrow-left',
        nextIcon: 'arrow-right',
        canPrev: false,
        canNext: true,
        hidden: false,
      },
    })

    await wrapper.find('.auto-turn-countdown').trigger('click')
    expect(wrapper.emitted('toggleAutoTurnPause')).toBeTruthy()
  })
})

describe('useAutoTurn Composable - Discrete Paged AutoTurn State Machine', () => {
  it('runs countdown in paged mode and stops in vertical-continuous mode', async () => {
    const { useAutoTurn } = await import('@/composables/useAutoTurn')
    const { ref, reactive, computed } = await import('vue')

    const settings = reactive<ReaderSettings>({
      ...DEFAULT_SETTINGS,
      mode: 'vertical-paged',
      autoTurn: true,
      autoTurnInterval: 10,
    })

    const currentGroupIndex = ref(0)
    const lastGroupIndex = computed(() => 5)
    const settingsOpen = ref(false)
    const onAdvance = () => {}

    const auto = useAutoTurn({
      settings,
      currentGroupIndex,
      lastGroupIndex,
      settingsOpen,
      onAdvance,
    })

    expect(auto.autoTurnPaused.value).toBe(false)
    expect(auto.canAutoTurnRun()).toBe(true)

    // Toggle pause
    auto.toggleAutoTurnPause()
    expect(auto.autoTurnPaused.value).toBe(true)
    expect(auto.canAutoTurnRun()).toBe(false)

    // Resume
    auto.toggleAutoTurnPause()
    expect(auto.autoTurnPaused.value).toBe(false)
    expect(auto.canAutoTurnRun()).toBe(true)

    // In vertical-continuous mode, canAutoTurnRun is false by design
    settings.mode = 'vertical-continuous'
    expect(auto.canAutoTurnRun()).toBe(false)
  })

  it('resets countdown when resetAutoTurnCountdown is called on user interaction in paged mode', async () => {
    const { useAutoTurn } = await import('@/composables/useAutoTurn')
    const { ref, reactive, computed } = await import('vue')

    const settings = reactive<ReaderSettings>({
      ...DEFAULT_SETTINGS,
      mode: 'horizontal',
      autoTurn: true,
      autoTurnInterval: 15,
    })

    const auto = useAutoTurn({
      settings,
      currentGroupIndex: ref(0),
      lastGroupIndex: computed(() => 5),
      settingsOpen: ref(false),
      onAdvance: () => {},
    })

    auto.autoTurnRemaining.value = 3
    auto.resetAutoTurnCountdown()
    expect(auto.autoTurnRemaining.value).toBe(15)
  })
})

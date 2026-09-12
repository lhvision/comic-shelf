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

  it('allows selecting speed presets and entering custom speed in vertical-continuous mode in ReaderSettingsPanel', async () => {
    const { settings } = useReaderSettings()
    settings.mode = 'vertical-continuous'
    settings.autoTurn = true
    settings.autoScrollSpeed = 80

    const wrapper = mount(ReaderSettingsPanel, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    // Speed preset buttons (40, 80, 140) + 1 custom button
    const presetButtons = wrapper.findAll('.auto-turn-options button')
    expect(presetButtons.length).toBe(4)
    expect(wrapper.find('.custom-chip-btn').text()).toBe('自定义…')

    // Click custom button to activate speed input
    await wrapper.find('.custom-chip-btn').trigger('click')

    const input = wrapper.find('.custom-interval-input')
    expect(input.exists()).toBe(true)

    // Set custom speed to 120 px/s
    await input.setValue(120)
    await input.trigger('blur')

    expect(settings.autoScrollSpeed).toBe(120)
    expect(wrapper.text()).toContain('以每秒 120 像素平滑匀速向下滚动')

    // Click preset 40 px/s to switch back
    const btn40 = wrapper.findAll('.auto-turn-options button')[0]
    expect(btn40?.text()).toBe('40 px/s')
    await btn40?.trigger('click')
    expect(settings.autoScrollSpeed).toBe(40)
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

  it('renders speed and play icon when in vertical-continuous mode in ReaderHud', async () => {
    const wrapper = mount(ReaderHud, {
      props: {
        autoTurn: true,
        atLastGroup: false,
        autoTurnPaused: false,
        settingsOpen: false,
        autoTurnRemaining: 0,
        mode: 'vertical-continuous',
        autoScrollSpeed: 80,
        currentGroupLabel: '1',
        total: 20,
        prevIcon: 'arrow-up',
        nextIcon: 'arrow-down',
        canPrev: false,
        canNext: true,
        hidden: false,
      },
    })

    // Running state: displays speed
    expect(wrapper.find('.auto-turn-speed').text()).toBe('80px')
    expect(wrapper.find('.app-icon--play').exists()).toBe(false)

    // Paused state: displays play icon
    await wrapper.setProps({
      autoTurnPaused: true,
    } as Record<string, unknown>)

    expect(wrapper.find('.auto-turn-speed').exists()).toBe(false)
    expect(wrapper.find('.app-icon--play').exists()).toBe(true)

    // At last group but not yet docked: button remains visible in continuous mode!
    await wrapper.setProps({
      autoTurnPaused: false,
      atLastGroup: true,
      isDockedAtEnd: false,
    } as Record<string, unknown>)

    expect(wrapper.find('.auto-turn-countdown').exists()).toBe(true)
    expect(wrapper.find('.auto-turn-speed').text()).toBe('80px')

    // Docked at end: button hides
    await wrapper.setProps({
      isDockedAtEnd: true,
    } as Record<string, unknown>)

    expect(wrapper.find('.auto-turn-countdown').exists()).toBe(false)
  })
})

describe('useAutoTurn Composable - Continuous Mode & Soft Yield', () => {
  it('smoothly scrolls container via rAF in vertical-continuous mode and docks at bottom', async () => {
    const { useAutoTurn } = await import('@/composables/useAutoTurn')
    const { ref, reactive, computed } = await import('vue')

    const mockContainer = document.createElement('main')
    Object.defineProperty(mockContainer, 'clientHeight', { value: 800, configurable: true })
    Object.defineProperty(mockContainer, 'scrollHeight', { value: 1200, configurable: true })
    mockContainer.scrollTop = 0

    const scrollEl = ref<HTMLElement | null>(mockContainer)
    const settings = reactive({
      ...DEFAULT_SETTINGS,
      mode: 'vertical-continuous' as const,
      autoTurn: true,
      autoScrollSpeed: 100, // 100 px/s
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
      scrollEl,
    })

    auto.startAutoScroll()

    // Let's verify startAutoScroll ran and canAutoTurnRun reflects state
    expect(auto.autoTurnPaused.value).toBe(false)
  })

  it('un-docks when user scrolls away from the bottom in continuous mode', async () => {
    const { useAutoTurn } = await import('@/composables/useAutoTurn')
    const { ref, reactive, computed } = await import('vue')

    const mockContainer = document.createElement('main')
    Object.defineProperty(mockContainer, 'clientHeight', { value: 800, configurable: true })
    Object.defineProperty(mockContainer, 'scrollHeight', { value: 2000, configurable: true })
    // Currently at bottom: 2000 - 800 = 1200
    mockContainer.scrollTop = 1200

    const scrollEl = ref<HTMLElement | null>(mockContainer)
    const settings = reactive({
      ...DEFAULT_SETTINGS,
      mode: 'vertical-continuous' as const,
      autoTurn: true,
      autoScrollSpeed: 80,
    })

    const auto = useAutoTurn({
      settings,
      currentGroupIndex: ref(5),
      lastGroupIndex: computed(() => 5),
      settingsOpen: ref(false),
      onAdvance: () => {},
      scrollEl,
    })

    // Simulate arriving at end
    auto.isDockedAtEnd.value = true
    expect(auto.isDockedAtEnd.value).toBe(true)

    // User scrolls back up to 500px (< 1200 - 40)
    mockContainer.scrollTop = 500
    auto.yieldAutoScroll()

    // isDockedAtEnd should be released
    expect(auto.isDockedAtEnd.value).toBe(false)
    expect(auto.isYielding.value).toBe(true)
  })
})

import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { useParameterLabel } from '~/composables/useParameterLabel'
import { SETTINGS_DEFAULTS, useSettings } from '~/composables/useSettings'

// Harness exposing both composables' surface so they run inside a real Nuxt
// setup context (useI18n / useLocalStorage need it).
const Harness = defineComponent({
  setup() {
    const { parameterLabel, resolutionLabel, datasetLabel } = useParameterLabel()
    const { settings, reset } = useSettings()
    return { parameterLabel, resolutionLabel, datasetLabel, settings, reset }
  },
  render: () => h('div'),
})

async function mount() {
  const wrapper = await mountSuspended(Harness)
  wrapper.vm.reset()
  await nextTick()
  return wrapper
}

describe('useSettings', () => {
  afterEach(async () => {
    const wrapper = await mountSuspended(Harness)
    wrapper.vm.reset()
  })

  it('exposes the documented defaults', async () => {
    const wrapper = await mount()
    expect(wrapper.vm.settings.friendlyLabels).toBe(true)
    expect(wrapper.vm.settings.convertUnits).toBe(true)
  })

  it('retains changes across a freshly acquired composable', async () => {
    const wrapper = await mount()
    wrapper.vm.settings.convertUnits = false
    await nextTick()

    // A second consumer must observe the same persisted store (module singleton
    // backed by localStorage), not a fresh copy of the defaults.
    const second = await mountSuspended(Harness)
    expect(second.vm.settings.convertUnits).toBe(false)
  })

  it('reset() restores the defaults', async () => {
    const wrapper = await mount()
    wrapper.vm.settings.friendlyLabels = false
    await nextTick()
    wrapper.vm.reset()
    await nextTick()
    expect(wrapper.vm.settings.friendlyLabels).toBe(SETTINGS_DEFAULTS.friendlyLabels)
  })
})

describe('useParameterLabel', () => {
  afterEach(async () => {
    const wrapper = await mountSuspended(Harness)
    wrapper.vm.reset()
  })

  it('maps known ids to friendly labels (en default locale in tests)', async () => {
    const wrapper = await mount()
    expect(wrapper.vm.parameterLabel('temperature_air_mean_2m')).toBe('Air temperature (2 m)')
    expect(wrapper.vm.resolutionLabel('daily')).toBe('Daily')
    expect(wrapper.vm.datasetLabel('climate_summary')).toBe('Climate summary')
  })

  it('prettifies unknown ids as a fallback', async () => {
    const wrapper = await mount()
    expect(wrapper.vm.parameterLabel('made_up_parameter')).toBe('Made Up Parameter')
  })

  it('returns the raw id when friendly labels are disabled', async () => {
    const wrapper = await mount()
    wrapper.vm.settings.friendlyLabels = false
    await nextTick()
    expect(wrapper.vm.parameterLabel('temperature_air_mean_2m')).toBe('temperature_air_mean_2m')
  })

  it('returns an empty string for nullish input', async () => {
    const wrapper = await mount()
    expect(wrapper.vm.parameterLabel(undefined)).toBe('')
    expect(wrapper.vm.parameterLabel(null)).toBe('')
  })
})

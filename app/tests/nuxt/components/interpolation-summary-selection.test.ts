import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import InterpolationSummarySelection from '~/components/InterpolationSummarySelection.vue'

const parameterSelection = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily' as const,
  dataset: 'climate_summary',
  parameters: ['temperature_air_mean_2m'],
}

const feldberg = {
  station_id: '02290',
  name: 'Feldberg',
  state: 'Baden-Württemberg',
  latitude: 47.9,
  longitude: 8.0,
  height: 1000,
}

registerEndpoint('/api/stations', () => ({ stations: [feldberg] }))

/**
 * Hold the model the way a parent does, so the component's writes come back to it.
 *
 * Through a ref rather than `setProps`, which lands a tick later and would have the component
 * reading a model it has already written to.
 */
async function selection(source: 'manual' | 'station') {
  const model = ref<Record<string, unknown>>({ source })
  const wrapper = await mountSuspended(defineComponent({
    setup: () => () => h(InterpolationSummarySelection as never, {
      'parameterSelection': parameterSelection,
      'modelValue': model.value,
      'onUpdate:modelValue': (value: Record<string, unknown>) => { model.value = value },
    }),
  }), { attachTo: document.body })
  // the tests assign the station directly, so nothing waits on the station list
  await flushPromises()
  const inner = wrapper.findComponent(InterpolationSummarySelection)
  return { wrapper, model, vm: inner.vm as any }
}

/** The watchers settle over a few ticks, one feeding the next. */
async function settle() {
  for (let index = 0; index < 6; index++)
    await nextTick()
}

describe('choosing the point an interpolation answers for', () => {
  it('keeps the station\'s height when its own source button is clicked again', async () => {
    // the button was treated as a change whichever source it named, so clicking the active one
    // dropped the height of a station that stayed selected: nothing moved on screen and the next
    // answer came back uncorrected, which at 1000 m is six degrees of air temperature
    const { model, vm } = await selection('station')
    vm.selectedStation = feldberg
    await settle()
    expect(model.value.elevation).toBe(1000)

    vm.setSource('station')
    await settle()
    expect(model.value.elevation).toBe(1000)
  })

  it('keeps hand-typed coordinates when the station source has nothing to offer', async () => {
    // clicking through to the station list and back was taking the empty answer of a select with
    // nothing chosen in it, and clearing coordinates someone had just typed
    const { model, vm } = await selection('manual')
    vm.latitudeInput = '52.52'
    vm.longitudeInput = '13.40'
    await settle()
    expect(model.value.latitude).toBe(52.52)

    vm.setSource('station')
    await settle()
    vm.setSource('manual')
    await settle()
    expect(model.value.latitude).toBe(52.52)
    expect(model.value.longitude).toBe(13.4)
  })

  it('lets go of a station the parent has cleared', async () => {
    // a provider or dataset change replaces the whole model, and a select still holding the old
    // station would write it back for a dataset that may not have it
    const { model, vm } = await selection('station')
    vm.selectedStation = feldberg
    await settle()
    expect(model.value.station).toBeTruthy()

    model.value = { source: 'manual' }
    await settle()
    vm.setSource('station')
    await settle()
    expect(model.value.station).toBeUndefined()
  })

  it('names the station\'s height again on returning to it', async () => {
    // the station never leaves the select, so its own watcher stays silent -- and the elevation
    // would otherwise stay empty against a form showing the station and its coordinates
    const { model, vm } = await selection('station')
    vm.selectedStation = feldberg
    await settle()

    vm.setSource('manual')
    await settle()
    expect(model.value.elevation).toBeUndefined()

    vm.setSource('station')
    await settle()
    expect(model.value.elevation).toBe(1000)
  })
})

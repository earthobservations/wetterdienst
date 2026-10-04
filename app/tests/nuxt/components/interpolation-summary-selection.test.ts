import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { getQuery, setResponseStatus } from 'h3'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
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
  region: 'Baden-Württemberg',
  latitude: 47.9,
  longitude: 8.0,
  elevation: 1000,
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
  it('keeps the station\'s elevation when its own source button is clicked again', async () => {
    // the button was treated as a change whichever source it named, so clicking the active one
    // dropped the elevation of a station that stayed selected: nothing moved on screen and the next
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

  it('names the station\'s elevation again on returning to it', async () => {
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

describe('the interpolation\'s station picker with postcode stations', () => {
  // dwd/derived climate_correction_factor's stations are postcodes, sent with a null name and a
  // null position
  const postcode = { station_id: '01067', name: null, region: null, latitude: null, longitude: null, elevation: null }

  it('labels a station without a name by its id', async () => {
    const nameless = { ...postcode, station_id: '01069', latitude: 51.0, longitude: 13.7 }
    const { wrapper, vm } = await selection('station')
    vm.stationsData = { stations: [nameless, feldberg] }
    vm.selectedStation = nameless
    await settle()

    expect(vm.stationItems.map((i: { label: string }) => i.label)).toEqual(['01069', 'Feldberg (02290)'])
    expect(vm.selectedStationItem.label).toBe('01069')
    wrapper.unmount()
  })

  it('leaves a station without a position out, as it has no point to offer', async () => {
    // chosen, it showed as the source of the point, yet left the point unset: Fetch stayed
    // disabled with nothing saying why
    const { wrapper, vm } = await selection('station')
    vm.stationsData = { stations: [postcode, feldberg, { ...postcode, station_id: '01069', latitude: 51.0 }] }
    await settle()

    expect(vm.stationItems.map((i: { value: string }) => i.value)).toEqual(['02290'])
    wrapper.unmount()
  })
})

describe('the interpolation\'s station list that could not be fetched', () => {
  it('asks /api/stations once for a request answered with a 500', async () => {
    // counted at the endpoint, which a request reaches however it is made
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    }))
    // a dataset of its own, so the list is not the one the tests above leave mounted
    const wrapper = await mountSuspended(InterpolationSummarySelection, {
      props: { parameterSelection: { ...parameterSelection, dataset: 'kl' }, modelValue: { source: 'station' } },
    })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked).toBeGreaterThan(0)
      expect(vm.stationsPending).toBe(false)
    })
    expect(asked).toBe(1)
  })
})

describe('the interpolation\'s station list answered with a 503 once', () => {
  it('asks /api/stations once more, and lists what that answer brings', async () => {
    // a 503 the first time only, as a proxy gives while the backend restarts
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      if (asked === 1) {
        setResponseStatus(event, 503)
        return { detail: 'Service Unavailable' }
      }
      return { stations: [feldberg] }
    }))
    // a dataset of its own, so the list is not one the tests above leave mounted
    const wrapper = await mountSuspended(InterpolationSummarySelection, {
      props: { parameterSelection: { ...parameterSelection, dataset: 'more_precip' }, modelValue: { source: 'station' } },
    })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.allStations).toHaveLength(1))
    expect(asked).toBe(2)
  })
})

describe('the interpolation\'s station list on a change of dataset', () => {
  it('asks /api/stations once for the new dataset', async () => {
    // useFetch refetched on its own as the query changed, and the watcher on the selection refreshed
    // as well: the endpoint saw the new dataset twice
    const asked: unknown[] = []
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked.push(getQuery(event).parameters)
      return { stations: [feldberg] }
    }))
    // datasets of their own, so neither list is one the tests above leave mounted
    const selected = ref({ ...parameterSelection, dataset: 'water_equiv' })
    const wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(InterpolationSummarySelection as never, { parameterSelection: selected.value, modelValue: { source: 'station' } }),
    }))
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.findComponent(InterpolationSummarySelection).vm as any
    await vi.waitFor(() => expect(vm.allStations).toHaveLength(1))

    selected.value = { ...selected.value, dataset: 'weather_phenomena' }
    await vi.waitFor(() => {
      expect(asked).toContain('daily/weather_phenomena')
      expect(vm.stationsPending).toBe(false)
    })
    await flushPromises()
    expect(asked).toEqual(['daily/water_equiv', 'daily/weather_phenomena'])
  })
})

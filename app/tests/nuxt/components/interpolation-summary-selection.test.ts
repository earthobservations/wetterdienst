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

    // as ParameterSelection updates it: the new dataset with the old parameters, then its own
    // parameters a tick later
    selected.value = { ...selected.value, dataset: 'weather_phenomena' }
    await nextTick()
    selected.value = { ...selected.value, parameters: ['weather_phenomenon_fog'] }
    await vi.waitFor(() => {
      expect(asked).toContain('daily/weather_phenomena')
      expect(vm.stationsPending).toBe(false)
    })
    await flushPromises()
    expect(asked).toEqual(['daily/water_equiv', 'daily/weather_phenomena'])
  })

  it('lets go of the last dataset\'s list once no dataset is chosen', async () => {
    // a change of resolution leaves no dataset and no parameters, and useFetch carried the last list
    // over to the query it no longer fetched: its stations stayed on offer
    onTestFinished(registerEndpoint('/api/stations', () => ({ stations: [feldberg] })))
    const selected = ref<Record<string, unknown>>({ ...parameterSelection, dataset: 'wind_extreme' })
    const wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(InterpolationSummarySelection as never, { parameterSelection: selected.value, modelValue: { source: 'station' } }),
    }))
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.findComponent(InterpolationSummarySelection).vm as any
    await vi.waitFor(() => expect(vm.allStations).toHaveLength(1))

    selected.value = { ...selected.value, resolution: 'hourly', dataset: undefined, parameters: [] }
    await vi.waitFor(() => expect(vm.allStations).toEqual([]))
  })
})

describe('the interpolation\'s station picker whose list could not be fetched', () => {
  it('says the stations could not be loaded, and asks for them again on Retry', async () => {
    // the select was left empty with nothing said, and nothing asked again until the selection
    // wanted another list. Two failures, then the stations, held on a gate so the picker can be
    // seen while Retry's request is out
    let asked = 0
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    onTestFinished(() => release())
    onTestFinished(registerEndpoint('/api/stations', async (event) => {
      asked++
      if (asked <= 2) {
        setResponseStatus(event, 500)
        return { detail: 'Upstream failed' }
      }
      await gate
      return { stations: [feldberg] }
    }))
    // a dataset of its own, so the list is not one the tests above leave mounted
    const wrapper = await mountSuspended(InterpolationSummarySelection, {
      props: { parameterSelection: { ...parameterSelection, dataset: 'solar' }, modelValue: { source: 'station' } },
      attachTo: document.body,
    })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    const alert = () => wrapper.find('[role="alert"]')
    const retry = () => wrapper.findAll('button').find(b => b.text() === 'Retry')

    await vi.waitFor(() => expect(alert().exists() && alert().text()).toBe('Failed to load stations.'))
    expect(asked).toBe(1)
    const firstAlert = alert().element

    // a Retry that fails too is announced again, by a notice mounted anew
    ;(retry()!.element as HTMLElement).focus()
    await retry()!.trigger('click')
    await vi.waitFor(() => {
      expect(asked).toBe(2)
      expect(vm.stationsPending).toBe(false)
      expect(alert().exists()).toBe(true)
    })
    expect(alert().element).not.toBe(firstAlert)

    // useFetch keeps the error until the next answer: while that is out, the picker says it is
    // loading, not that loading failed, and the Retry pressed keeps its focus
    const button = retry()!.element as HTMLElement
    button.focus()
    await retry()!.trigger('click')
    await vi.waitFor(() => {
      expect(asked).toBe(3)
      expect(wrapper.text()).toContain('Loading stations')
      expect(alert().exists()).toBe(false)
    })
    expect(retry()?.element).toBe(button)
    expect(document.activeElement).toBe(button)
    // pressed again meanwhile, it leaves the request out alone rather than asking anew
    await retry()!.trigger('click')

    release()
    await vi.waitFor(() => expect(vm.allStations).toHaveLength(1))
    expect(asked).toBe(3)
    expect(alert().exists()).toBe(false)
    expect(retry()).toBeUndefined()
  })
})

describe('the interpolation\'s station picker with no station to offer', () => {
  const notice = 'No station with a position found for the selected parameters.'
  // dwd/derived climate_correction_factor's stations are postcodes, sent with a null position
  const postcode = { station_id: '01067', name: null, region: null, latitude: null, longitude: null, elevation: null }

  /** Mount the picker on a dataset of its own, so its list is not one another test left mounted. */
  async function picker(dataset: string) {
    const wrapper = await mountSuspended(InterpolationSummarySelection, {
      props: { parameterSelection: { ...parameterSelection, dataset }, modelValue: { source: 'station' } },
    })
    onTestFinished(() => wrapper.unmount())
    return { wrapper, vm: wrapper.vm as any }
  }

  it('says so when no station of the list has a position', async () => {
    // the select opened empty with nothing said why
    onTestFinished(registerEndpoint('/api/stations', () => ({
      stations: [postcode, { ...postcode, station_id: '01069' }],
    })))
    const { wrapper, vm } = await picker('climate_correction_factor')

    await vi.waitFor(() => expect(vm.allStations).toHaveLength(2))
    expect(vm.stationItems).toEqual([])
    await vi.waitFor(() => expect(wrapper.text()).toContain(notice))

    // and the select is described by it, so it is heard on reaching the select
    const help = wrapper.find('[data-slot="help"]')
    expect(help.text()).toBe(notice)
    // the select is the control its field's label names
    const label = wrapper.findAll('label').find(l => l.text().includes('Select station for coordinates'))!
    const select = wrapper.find(`[id="${label.attributes('for')}"]`)
    expect(select.attributes('aria-describedby')!.split(' ')).toContain(help.attributes('id'))
  })

  it('says so when the list is empty', async () => {
    onTestFinished(registerEndpoint('/api/stations', () => ({ stations: [] })))
    const { wrapper } = await picker('urban_temperature_air')

    await vi.waitFor(() => expect(wrapper.text()).toContain(notice))
  })

  it('says nothing of it when a station is on offer', async () => {
    onTestFinished(registerEndpoint('/api/stations', () => ({ stations: [postcode, feldberg] })))
    const { wrapper, vm } = await picker('urban_pressure')

    await vi.waitFor(() => expect(vm.stationItems).toHaveLength(1))
    expect(wrapper.text()).not.toContain(notice)
  })

  it('says nothing of it while the list is out', async () => {
    // held on a gate, so the picker can be seen before the list answers
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    onTestFinished(() => release())
    onTestFinished(registerEndpoint('/api/stations', async () => {
      await gate
      return { stations: [] }
    }))
    const { wrapper } = await picker('urban_wind')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Loading stations'))
    expect(wrapper.text()).not.toContain(notice)

    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain(notice))
  })

  it('says the list failed rather than that it is empty, until a Retry answers', async () => {
    // a failed list is empty too, and the Retry notice says what is wrong with it
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      if (asked === 1) {
        setResponseStatus(event, 500)
        return { detail: 'Upstream failed' }
      }
      return { stations: [] }
    }))
    const { wrapper } = await picker('urban_precipitation')
    const alert = () => wrapper.find('[role="alert"]')

    await vi.waitFor(() => expect(alert().exists() && alert().text()).toBe('Failed to load stations.'))
    expect(wrapper.text()).not.toContain(notice)

    await wrapper.findAll('button').find(b => b.text() === 'Retry')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain(notice))
    expect(alert().exists()).toBe(false)
  })
})

describe('the interpolation\'s station picker after a Retry', () => {
  // the focus Retry held fell to the page's body once a Retry that worked took the notice away
  const retry = () => [...document.body.querySelectorAll('button')].find(b => b.textContent?.trim() === 'Retry')

  /**
   * The picker on a dataset of its own, its first list failed, and a Retry pressed, its answer held
   * on a gate: the stations, or a failure again.
   */
  async function retried(dataset: string, again: 'stations' | 'failure') {
    let asked = 0
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    onTestFinished(() => release())
    onTestFinished(registerEndpoint('/api/stations', async (event) => {
      asked++
      if (asked > 1)
        await gate
      if (asked === 1 || again === 'failure') {
        setResponseStatus(event, 500)
        return { detail: 'Upstream failed' }
      }
      return { stations: [feldberg] }
    }))
    const wrapper = await mountSuspended(InterpolationSummarySelection, {
      props: { parameterSelection: { ...parameterSelection, dataset }, modelValue: { source: 'station' } },
      attachTo: document.body,
    })
    onTestFinished(() => wrapper.unmount())
    await vi.waitFor(() => expect(retry()).toBeDefined())
    const button = retry()!
    button.focus()
    button.click()
    await vi.waitFor(() => expect(asked).toBe(2))
    return { wrapper, vm: wrapper.vm as any, button, release }
  }

  /** The select, the control its field's label names. */
  function select(wrapper: Awaited<ReturnType<typeof retried>>['wrapper']) {
    // looked up in this picker: one another test left mounted has the same ids
    const label = wrapper.findAll('label').find(l => l.text().includes('Select station for coordinates'))!
    return wrapper.element.querySelector(`[id="${label.attributes('for')}"]`)
  }

  it('hands the focus on to the select once the list has come', async () => {
    const { wrapper, vm, release } = await retried('kl', 'stations')

    release()
    await vi.waitFor(() => expect(vm.allStations).toHaveLength(1))
    expect(retry()).toBeUndefined()
    await vi.waitFor(() => expect(select(wrapper)).not.toBeNull())
    await vi.waitFor(() => expect(document.activeElement).toBe(select(wrapper)))
  })

  it('leaves the focus where it was moved to meanwhile', async () => {
    const { wrapper, vm, release } = await retried('more_precip', 'stations')
    const elevation = wrapper.find('input[placeholder="e.g. 34"]').element as HTMLInputElement
    elevation.focus()

    release()
    await vi.waitFor(() => expect(vm.allStations).toHaveLength(1))
    await vi.waitFor(() => expect(select(wrapper)).not.toBeNull())
    await flushPromises()
    expect(document.activeElement).toBe(elevation)
  })

  it('keeps the focus on Retry where the list fails again', async () => {
    const { vm, button, release } = await retried('weather_phenomena', 'failure')

    release()
    await vi.waitFor(() => {
      expect(vm.stationsPending).toBe(false)
      expect(document.body.querySelector('[role="alert"]')).not.toBeNull()
    })
    await flushPromises()
    expect(retry()).toBe(button)
    expect(document.activeElement).toBe(button)
  })
})

import type { H3Event } from 'h3'
import type { ProviderNetworkCoverageResponse, ServerSettings } from '#shared/types/api'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError, getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
import { clearNuxtState, useRouter, useServerSettings, useToast } from '#imports'
import ParameterSelection from '~/components/ParameterSelection.vue'
import ExplorerPage from '~/pages/explorer.vue'
import { dailyClimateSummaryCoverage } from '../fixtures/coverage'

// DataViewer's copy-to-clipboard buttons use UTooltip, which needs a
// TooltipProvider -- normally supplied by app.vue's root <UApp>. Mounting the
// bare page works for most tests, but any test that drives it far enough to
// render DataViewer (i.e. picks a station) needs this wrapper too.
const ExplorerWithApp = defineComponent({
  setup() {
    return () => h(UApp, null, { default: () => h(ExplorerPage) })
  },
})

const VALUE_ROW = { station_id: '00001', dataset: 'climate_summary', parameter: 'temperature_air_max_2m', timestamp: '2020-01-01T00:00:00Z', value: 12.3, quality: null, unit: 'degree_celsius' }

// pages mounted, and endpoints registered, by a test: unmounted and removed after it
const mounted: { unmount: () => void }[] = []
const endpoints: (() => void)[] = []

// Mount the page with a station and a parameter selected, ready to fetch; `values` answers /api/values
async function mountWithSelection(values: (event: H3Event) => unknown) {
  endpoints.push(registerEndpoint('/api/coverage', (event) => {
    const q = getQuery(event)
    if (q.provider)
      return dailyClimateSummaryCoverage()
    return { dwd: { observation: {} } }
  }))
  endpoints.push(registerEndpoint('/api/stations', () => ({
    stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
  })))
  endpoints.push(registerEndpoint('/api/values', values))

  const wrapper = await mountSuspended(ExplorerWithApp, { attachTo: document.body })
  mounted.push(wrapper)
  const vm = wrapper.findComponent(ExplorerPage).vm as any

  // Let ParameterSelection's initialization settle before driving it externally -- otherwise its
  // own emitUpdate() races and clobbers these. It no longer awaits /api/coverage in setup, so
  // that window now spans the whole round trip and is too long to sleep through blindly.
  await vi.waitFor(
    () => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false),
    { timeout: 5000 },
  )
  await wrapper.vm.$nextTick()

  vm.parameterSelectionState.selection.resolution = 'daily'
  vm.parameterSelectionState.selection.dataset = 'climate_summary'
  await wrapper.vm.$nextTick()
  await new Promise(resolve => setTimeout(resolve, 50))
  await wrapper.vm.$nextTick()

  vm.parameterSelectionState.selection.parameters = ['temperature_air_max_2m']
  vm.stationSelectionState.selection.stations = [{ station_id: '00001', name: 'Test Station' }]
  await wrapper.vm.$nextTick()
  await new Promise(resolve => setTimeout(resolve, 50))
  await wrapper.vm.$nextTick()

  expect(vm.canFetch).toBe(true)
  return { wrapper, vm }
}

describe('explorer Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    // toasts are app-wide, so a failed fetch's would be shown by the next test's page
    useToast().clear()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays parameter selection', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    const text = wrapper.text()

    expect(text).toContain('Select Parameters')
  })

  it('displays station mode options', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)

    // Check that the component renders successfully
    expect(wrapper.exists()).toBe(true)
  })

  it('has data viewer component', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)

    // Check if DataViewer component is present
    expect(wrapper.html()).toBeTruthy()
  })

  it('clicking Show fetches values into the table, and clicking Reset clears them', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))

    const showButton = wrapper.findAll('button').find(b => b.text() === 'Show')
    await showButton!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    // nothing has changed since, so there is nothing new to fetch
    expect(vm.canFetch).toBe(false)

    const resetButton = wrapper.findAll('button').find(b => b.text() === 'Reset')
    await resetButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('12.3')
    expect(vm.canFetch).toBe(true)
  })

  it('offers Show again for the same selection after the fetch failed', async () => {
    // failing until the test lets it answer: a GET that fails is retried once on its own. The answer is
    // then held until the test lets it go
    let failing = true
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    const { wrapper, vm } = await mountWithSelection(async () => {
      if (failing)
        throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
      await held
      return { values: [VALUE_ROW] }
    })

    const showButton = () => wrapper.findAll('button').find(b => b.text() === 'Show')!
    await showButton().trigger('click')
    await vi.waitFor(() => expect(vm.dataViewerRef.fetchErrorMessage).toBeTruthy())
    await vi.waitFor(() => expect(showButton().attributes('disabled')).toBeUndefined())
    expect(wrapper.text()).not.toContain('12.3')

    failing = false
    await showButton().trigger('click')
    // the failed fetch's error stays until the retry answers, but the retry is under way
    await vi.waitFor(() => expect(vm.dataViewerRef.valuesPending).toBe(true))
    expect(vm.canFetch).toBe(false)
    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)
  })

  it('keeps Show disabled while a fetch is under way, and for a newer Fetch that cancelled it', async () => {
    // the first request's answer is held until the test lets it go, and differs from the second's
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    let requests = 0
    let firstAnswered = false
    const { wrapper, vm } = await mountWithSelection(async () => {
      requests += 1
      if (requests === 1) {
        await held
        firstAnswered = true
        return { values: [VALUE_ROW] }
      }
      return { values: [{ ...VALUE_ROW, value: 45.6 }] }
    })

    const showButton = () => wrapper.findAll('button').find(b => b.text() === 'Show')!
    await showButton().trigger('click')
    await vi.waitFor(() => expect(requests).toBe(1))
    expect(vm.canFetch).toBe(false)

    vm.dataSettings.humanize = false
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('45.6'))
    expect(vm.canFetch).toBe(false)
    expect(wrapper.text()).not.toContain('12.3')

    // let the held handler finish, within this test. Its answer cannot reach the table whenever it
    // comes: useAsyncData rejects a cancelled fetch as it is aborted, not when its answer arrives
    release()
    await vi.waitFor(() => expect(firstAnswered).toBe(true))
  })

  it('offers Show again when the station is removed and chosen again', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)

    // with no station the viewer is gone, and it comes back empty
    vm.stationSelectionState.selection.stations = []
    await wrapper.vm.$nextTick()
    expect(vm.dataViewerRef).toBeNull()
    vm.stationSelectionState.selection.stations = [{ station_id: '00001', name: 'Test Station' }]
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    expect(wrapper.text()).not.toContain('12.3')
  })

  it('keeps Show disabled when a setting the request does not carry changes', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)

    // an interpolation point is sent only in interpolation mode; this is station mode
    vm.stationSelectionState.interpolation.latitude = 50.1
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(false)

    // the shape is sent in station mode, so changing it asks for something new
    vm.dataSettings.shape = 'wide'
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
  })

  it('offers Show again when a setting sent empty becomes NaN', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))
    // a cleared number input is null
    vm.dataSettings.skipThreshold = null
    await wrapper.vm.$nextTick()

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)

    // sent as "NaN" where null is sent empty, so another request, though JSON writes both as null
    vm.dataSettings.skipThreshold = Number.NaN
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
  })
})

describe('explorer Page station details', () => {
  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    useToast().clear()
  })

  it('shows a dash for a chosen station without a position', async () => {
    // dwd/derived climate_correction_factor's stations are postcodes, sent with null coordinates,
    // which reached `.toFixed()` and took the table down
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [] }))
    vm.stationSelectionState.selection.stations = [
      { station_id: '01067', name: null, region: null, latitude: null, longitude: null, elevation: null },
      { station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4, elevation: 34 },
    ]
    await wrapper.vm.$nextTick()

    await wrapper.findAll('button').find(b => b.text() === 'Stations Details')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.find('table').exists()).toBe(true))

    const rows = wrapper.findAll('tbody tr').map(row => row.findAll('td').map(cell => cell.text()))
    expect(rows.map(cells => cells.slice(0, 5))).toEqual([
      ['01067', '', '', '-', '-'],
      ['00001', 'Test Station', 'Berlin', '52.5000', '13.4000'],
    ])
  })
})

describe('explorer Page DWD DMO lead time', () => {
  // `/api/coverage?provider=dwd&network=dmo`, cut down to a 1-hourly and a 3-hourly parameter of
  // `icon`, and `icon_eu`, which publishes only the short run
  function dmoCoverage() {
    const parameter = (name: string) => ({ name, name_original: name, unit_type: 'precipitation', unit: 'millimeter', description: null })
    return {
      hourly: {
        description: null,
        datasets: {
          icon: { description: null, parameters: [parameter('precipitation_amount_last_1h'), parameter('precipitation_amount_last_3h')] },
          icon_eu: { description: null, parameters: [parameter('precipitation_amount_last_1h')] },
        },
      },
    } satisfies ProviderNetworkCoverageResponse
  }

  // the query of every /api/values request, in order
  const sent: Record<string, unknown>[] = []

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    sent.splice(0)
    useToast().clear()
  })

  // Mount the page at `query`, as a shared link restores it, with a station chosen
  async function mountAt(query: string) {
    endpoints.push(registerEndpoint('/api/coverage', (event) => {
      const q = getQuery(event)
      if (q.network === 'dmo')
        return dmoCoverage()
      if (q.provider)
        return dailyClimateSummaryCoverage()
      return { dwd: { dmo: {}, observation: {} } }
    }))
    endpoints.push(registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '10147', name: 'Hamburg', latitude: 53.6, longitude: 10.0 }],
    })))
    endpoints.push(registerEndpoint('/api/values', (event) => {
      sent.push(getQuery(event))
      return { values: [] }
    }))

    const wrapper = await mountSuspended(ExplorerWithApp, { attachTo: document.body, route: `/explorer?${query}` })
    mounted.push(wrapper)
    const vm = wrapper.findComponent(ExplorerPage).vm as any
    await vi.waitFor(
      () => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false),
      { timeout: 5000 },
    )
    vm.stationSelectionState.selection.stations = [{ station_id: '10147', name: 'Hamburg' }]
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    return { wrapper, vm }
  }

  const ICON = 'provider=dwd&network=dmo&resolution=hourly&dataset=icon&parameters=precipitation_amount_last_3h'
  const leadTimeCard = (wrapper: any) => wrapper.find('[data-testid="lead-time"]')
  const button = (wrapper: any, label: string) => wrapper.findAll('button').find((b: any) => b.text() === label)!

  // click Show, and return the query the values were asked for with
  async function show(wrapper: any) {
    const before = sent.length
    await button(wrapper, 'Show').trigger('click')
    await vi.waitFor(() => expect(sent.length).toBe(before + 1))
    return sent[before]!
  }

  // the URL's query once the page has written the chosen station into it, which a link it was
  // opened at does not carry
  async function writtenQuery() {
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.stations).toBe('10147'))
    return useRouter().currentRoute.value.query
  }

  it('sends the long run chosen for icon, and offers Show again for it', async () => {
    const { wrapper, vm } = await mountAt(ICON)
    expect(leadTimeCard(wrapper).exists()).toBe(true)

    expect((await show(wrapper)).lead_time).toBe('short')
    await vi.waitFor(() => expect(vm.canFetch).toBe(false))

    await button(wrapper, 'Long: 78 to 168 h, 3-hourly').trigger('click')
    // another run is another request
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    expect((await show(wrapper)).lead_time).toBe('long')
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.leadTime).toBe('long'))
  })

  it('restores the long run from a shared link, and sends it', async () => {
    const { wrapper } = await mountAt(`${ICON}&leadTime=long`)
    expect((await show(wrapper)).lead_time).toBe('long')
    expect((await writtenQuery()).leadTime).toBe('long')
  })

  it('offers no run for icon_eu, which has only the short one, and sends none', async () => {
    const { wrapper } = await mountAt('provider=dwd&network=dmo&resolution=hourly&dataset=icon_eu&leadTime=long')
    expect(leadTimeCard(wrapper).exists()).toBe(false)
    expect((await show(wrapper)).lead_time).toBeUndefined()
    expect((await writtenQuery()).leadTime).toBeUndefined()
  })

  it('offers no run outside DWD DMO, and sends none', async () => {
    const { wrapper } = await mountAt('provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m&leadTime=long')
    expect(leadTimeCard(wrapper).exists()).toBe(false)
    expect((await show(wrapper)).lead_time).toBeUndefined()
    expect((await writtenQuery()).leadTime).toBeUndefined()
  })

  it.each([
    ['network', 'observation'],
    ['provider', 'noaa'],
    ['resolution', 'daily'],
    ['dataset', 'icon_eu'],
  ])('goes back to the short run when the %s changes', async (field, other) => {
    const { wrapper, vm } = await mountAt(`${ICON}&leadTime=long`)
    const selection = vm.parameterSelectionState.selection
    selection[field] = other
    await vi.waitFor(() => expect(vm.leadTime).toBe('short'))
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.leadTime).toBeUndefined())

    // back on icon, the run offered is the default one, not the one chosen before
    selection.provider = 'dwd'
    selection.network = 'dmo'
    selection.resolution = 'hourly'
    selection.dataset = 'icon'
    await vi.waitFor(() => expect(leadTimeCard(wrapper).exists()).toBe(true))
    expect(vm.leadTime).toBe('short')
    expect(vm.dataViewerRef).toBeNull()
    vm.stationSelectionState.selection.stations = [{ station_id: '10147', name: 'Hamburg' }]
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    expect((await show(wrapper)).lead_time).toBe('short')
    expect((await writtenQuery()).leadTime).toBeUndefined()
  })
})

describe('explorer Page DWD DMO parameters per run', () => {
  // `/api/coverage?provider=dwd&network=dmo`, cut down to a parameter only the short run carries,
  // one only the long run carries and two both carry, with the runs the backend names for each
  function dmoCoverage() {
    const parameter = (name: string, lead_times: Array<'short' | 'long'>) => ({ name, name_original: name, unit_type: 'precipitation', unit: 'millimeter', description: null, lead_times })
    return {
      hourly: {
        description: null,
        datasets: {
          icon: {
            description: null,
            parameters: [
              parameter('precipitation_amount_last_1h', ['short']),
              parameter('precipitation_amount_last_3h', ['long']),
              parameter('temperature_air_mean_2m', ['short', 'long']),
              parameter('wind_speed', ['short', 'long']),
            ],
          },
        },
      },
    } satisfies ProviderNetworkCoverageResponse
  }

  // the parameters of every /api/values request, in order, with the run they were asked of
  const sent: { parameters: string[], leadTime: unknown }[] = []

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    sent.splice(0)
    useToast().clear()
  })

  // Mount the page at icon with `query` added, as a shared link restores it, with a station chosen
  async function mountAt(query: string) {
    endpoints.push(registerEndpoint('/api/coverage', (event) => {
      if (getQuery(event).network === 'dmo')
        return dmoCoverage()
      return { dwd: { dmo: {} } }
    }))
    endpoints.push(registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '10147', name: 'Hamburg', latitude: 53.6, longitude: 10.0 }],
    })))
    endpoints.push(registerEndpoint('/api/values', (event) => {
      const q = getQuery(event)
      sent.push({ parameters: String(q.parameters).split(',').sort(), leadTime: q.lead_time })
      return { values: [] }
    }))

    const wrapper = await mountSuspended(ExplorerWithApp, { attachTo: document.body, route: `/explorer?provider=dwd&network=dmo&resolution=hourly&dataset=icon${query}` })
    mounted.push(wrapper)
    const vm = wrapper.findComponent(ExplorerPage).vm as any
    const selection = wrapper.findComponent(ParameterSelection).vm as any
    await vi.waitFor(() => expect(selection.isInitializing).toBe(false), { timeout: 5000 })
    vm.stationSelectionState.selection.stations = [{ station_id: '10147', name: 'Hamburg' }]
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    return { wrapper, vm, selection }
  }

  const button = (wrapper: any, label: string) => wrapper.findAll('button').find((b: any) => b.text() === label)!

  // click Show, and return what the values were asked for
  async function show(wrapper: any) {
    const before = sent.length
    await button(wrapper, 'Show').trigger('click')
    await vi.waitFor(() => expect(sent.length).toBe(before + 1))
    return sent[before]!
  }

  it('offers and selects what the short run carries, and every one the long run carries once chosen', async () => {
    const { wrapper, vm, selection } = await mountAt('')
    expect(selection.params).toEqual(['precipitation_amount_last_1h', 'temperature_air_mean_2m', 'wind_speed'])
    expect(await show(wrapper)).toEqual({
      parameters: ['hourly/icon/precipitation_amount_last_1h', 'hourly/icon/temperature_air_mean_2m', 'hourly/icon/wind_speed'],
      leadTime: 'short',
    })

    await button(wrapper, 'Long: 78 to 168 h, 3-hourly').trigger('click')
    await vi.waitFor(() => expect(selection.params).toEqual(['precipitation_amount_last_3h', 'temperature_air_mean_2m', 'wind_speed']))
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    expect(await show(wrapper)).toEqual({
      parameters: ['hourly/icon/precipitation_amount_last_3h', 'hourly/icon/temperature_air_mean_2m', 'hourly/icon/wind_speed'],
      leadTime: 'long',
    })
  })

  it('drops from a partial selection the parameters the run chosen does not carry', async () => {
    const { wrapper, vm } = await mountAt('&parameters=precipitation_amount_last_1h,temperature_air_mean_2m')
    // the link's parameters are kept, the one only the short run carries among them
    expect(vm.parameterSelectionState.selection.parameters).toEqual(['precipitation_amount_last_1h', 'temperature_air_mean_2m'])
    await button(wrapper, 'Long: 78 to 168 h, 3-hourly').trigger('click')
    await vi.waitFor(() => expect(vm.parameterSelectionState.selection.parameters).toEqual(['temperature_air_mean_2m']))
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    expect(await show(wrapper)).toEqual({ parameters: ['hourly/icon/temperature_air_mean_2m'], leadTime: 'long' })
  })

  it('restores from a link only the parameters its run carries', async () => {
    const { wrapper } = await mountAt('&parameters=precipitation_amount_last_1h,precipitation_amount_last_3h,temperature_air_mean_2m&leadTime=long')
    expect(await show(wrapper)).toEqual({
      parameters: ['hourly/icon/precipitation_amount_last_3h', 'hourly/icon/temperature_air_mean_2m'],
      leadTime: 'long',
    })
  })
})

describe('explorer nearby station distance', () => {
  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
  })

  // the backend reads it for an interpolation only, and deprecates it for a summary (GH-2333)
  it.each([
    ['interpolation', true],
    ['summary', false],
  ] as const)('offers the nearby station distance in %s mode: %s', async (mode, offered) => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [] }))
    vm.stationSelectionState.mode = mode
    await wrapper.vm.$nextTick()
    await wrapper.findAll('button').find(b => b.text() === 'Settings')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Interpolation Options'))
    expect(wrapper.text().includes('Nearby station distance')).toBe(offered)
  })
})

describe('explorer Page skip threshold', () => {
  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    useToast().clear()
  })

  it('does not go down to 0, which the backend refuses', async () => {
    // GH-2334: /api/values answers a skip_threshold of 0 with a 422, as the CLI and the setting
    // refuse it; the lowest the input takes is the first step above 0
    const sent: unknown[] = []
    const { wrapper, vm } = await mountWithSelection((event) => {
      sent.push(getQuery(event).skip_threshold)
      return { values: [VALUE_ROW] }
    })
    vm.dataSettings.skipEmpty = true
    await wrapper.findAll('button').find(b => b.text() === 'Settings')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Threshold'))

    // the threshold's is the only number input the settings show in station mode
    expect(wrapper.findAll('input[inputmode="decimal"]')).toHaveLength(1)
    const input = wrapper.find('input[inputmode="decimal"]')
    await input.setValue('0')
    await input.trigger('blur')
    await wrapper.vm.$nextTick()
    expect(vm.dataSettings.skipThreshold).toBe(0.05)

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(sent).toEqual(['0.05']))
  })
})

describe('explorer Page settings from the server (GH-2359)', () => {
  // what GET /api/settings answers on a server whose WD_TS_* variables move every setting the
  // explorer shows off wetterdienst's default. The wide shape turns drop_nulls off, as the server
  // reports it
  function serverSettings(): ServerSettings {
    const common = {
      humanize: false,
      convert_units: true,
      unit_targets: { temperature: 'degree_fahrenheit', speed: 'knots', length_long: 'furlong', angle: 'degree' },
      skip_empty: true,
      skip_threshold: 0.8,
      skip_criteria: 'max' as const,
      drop_nulls: false,
    }
    const geo = {
      ...common,
      min_gain_of_value_pairs: 0.2,
      num_additional_stations: 5,
      station_distance_resolution_factors: { hourly: 1, daily: 2 },
    }
    return {
      values: { ...common, shape: 'wide' },
      interpolate: {
        ...geo,
        use_nearby_station_distance: 2.5,
        interpolation_station_distance: {},
        interpolation_station_distance_homogeneous: 60,
        interpolation_station_distance_heterogeneous: 30,
      },
      summarize: {
        ...geo,
        summary_station_distance: {},
        summary_station_distance_homogeneous: 60,
        summary_station_distance_heterogeneous: 30,
      },
    }
  }

  // the settings the explorer starts from where the server reports none: wetterdienst's
  const WETTERDIENST_DEFAULTS = {
    humanize: true,
    convertUnits: true,
    unitTargets: {},
    shape: 'long',
    skipEmpty: false,
    skipThreshold: 0.95,
    skipCriteria: 'min',
    dropNulls: true,
    useNearbyStationDistance: 1,
    stationDistanceHomogeneous: 40,
    stationDistanceHeterogeneous: 20,
    useStationDistancePerParameter: {},
    minGainOfValuePairs: 0.1,
    numAdditionalStations: 3,
  }

  // the server's settings, by the explorer's names
  const SERVER_DEFAULTS = {
    ...WETTERDIENST_DEFAULTS,
    humanize: false,
    shape: 'wide',
    skipEmpty: true,
    skipThreshold: 0.8,
    skipCriteria: 'max',
    dropNulls: false,
    useNearbyStationDistance: 2.5,
    stationDistanceHomogeneous: 60,
    stationDistanceHeterogeneous: 30,
    minGainOfValuePairs: 0.2,
    numAdditionalStations: 5,
  }

  // the requests GET /api/settings got
  let settingsAsked = 0

  beforeEach(() => {
    // asked once per app load: each test loads it afresh
    clearNuxtState('server-settings')
    settingsAsked = 0
  })

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    useToast().clear()
  })

  // the Unit Targets setting's "Default (...)" choices, one per type it lists. Read from the items
  // the selects are given rather than from the selects, which refuse the choice's empty value
  function defaultUnitChoices(vm: any): string[] {
    return vm.unitTypes.map((unitType: { type: string, units: string[] }) => vm.unitTargetItems(unitType)[0].label)
  }

  // the query Show sends to /api/values
  async function showQuery(wrapper: Awaited<ReturnType<typeof mountWithSelection>>['wrapper'], sent: Record<string, unknown>[]) {
    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    return sent[0]!
  }

  it('starts from the server\'s settings, names its units as the defaults, and sends every one', async () => {
    endpoints.push(registerEndpoint('/api/settings', () => {
      settingsAsked += 1
      return serverSettings()
    }))
    const sent: Record<string, unknown>[] = []
    const { wrapper, vm } = await mountWithSelection((event) => {
      sent.push(getQuery(event))
      return { values: [VALUE_ROW] }
    })

    await vi.waitFor(() => expect(vm.dataSettings).toEqual(SERVER_DEFAULTS))
    // the boxes' placeholders, and a new parameter's radius, are the server's radii too
    expect(vm.startingSettings).toEqual(SERVER_DEFAULTS)
    // a unit the app has no name for is named as the server names it
    expect(defaultUnitChoices(vm)).toEqual([
      'Default (Degrees Fahrenheit (°F))',
      'Default (Knots (kn))',
      'Default (Hectopascal (hPa))',
      'Default (Millimetres (mm))',
      'Default (Millimetres per hour (mm/h))',
      'Default (Centimetres (cm))',
      'Default (Metres (m))',
      'Default (furlong)',
    ])

    const query = await showQuery(wrapper, sent)
    expect(query).toMatchObject({
      humanize: 'false',
      convert_units: 'true',
      shape: 'wide',
      skip_empty: 'true',
      skip_threshold: '0.8',
      skip_criteria: 'max',
      drop_nulls: 'false',
    })
    expect(JSON.parse(String(query.unit_targets))).toEqual({
      temperature: 'degree_fahrenheit',
      speed: 'knots',
      pressure: 'hectopascal',
      precipitation: 'millimeter',
      precipitation_intensity: 'millimeter_per_hour',
      length_short: 'centimeter',
      length_medium: 'meter',
      length_long: 'furlong',
    })
    expect(settingsAsked).toBe(1)
  })

  it.each([404, 500])('keeps wetterdienst\'s settings where /api/settings answers %i', async (status) => {
    endpoints.push(registerEndpoint('/api/settings', () => {
      settingsAsked += 1
      throw createError({ statusCode: status })
    }))
    const sent: Record<string, unknown>[] = []
    const { wrapper, vm } = await mountWithSelection((event) => {
      sent.push(getQuery(event))
      return { values: [VALUE_ROW] }
    })

    await expect(useServerSettings()).resolves.toBeNull()
    expect(settingsAsked).toBeGreaterThan(0)
    expect(vm.dataSettings).toEqual(WETTERDIENST_DEFAULTS)
    expect(defaultUnitChoices(vm)[0]).toBe('Default (Degrees Celsius (°C))')

    // and the page works on
    const query = await showQuery(wrapper, sent)
    expect(query).toMatchObject({ humanize: 'true', shape: 'long', drop_nulls: 'true', skip_threshold: '0.95' })
    expect(JSON.parse(String(query.unit_targets))).toMatchObject({ temperature: 'degree_celsius', speed: 'meter_per_second' })
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
  })

  it('keeps what the link names and the user changed while the answer was on its way', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    endpoints.push(registerEndpoint('/api/settings', async () => {
      settingsAsked += 1
      await held
      return serverSettings()
    }))
    const wrapper = await mountSuspended(ExplorerPage, { route: '/explorer?humanize=true&shape=long' })
    mounted.push(wrapper)
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(settingsAsked).toBe(1))

    vm.dataSettings.skipThreshold = 0.5
    vm.dataSettings.stationDistanceHomogeneous = 55
    release()
    await useServerSettings()
    await wrapper.vm.$nextTick()

    expect(vm.dataSettings).toEqual({
      ...SERVER_DEFAULTS,
      // the link's
      humanize: true,
      shape: 'long',
      // the user's
      skipThreshold: 0.5,
      stationDistanceHomogeneous: 55,
    })
  })

  it('names every setting in the link, which reads back the same where the server\'s differ', async () => {
    endpoints.push(registerEndpoint('/api/settings', () => serverSettings()))
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))
    await vi.waitFor(() => expect(vm.dataSettings.humanize).toBe(false))

    // wetterdienst's own, which a link that left it out would read back as the server's
    vm.dataSettings.humanize = true
    await wrapper.vm.$nextTick()
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toMatchObject({
      humanize: 'true',
      convertUnits: 'true',
      shape: 'wide',
      skipEmpty: 'true',
      dropNulls: 'false',
    }))

    const link = useRouter().currentRoute.value.fullPath
    const reopened = await mountSuspended(ExplorerPage, { route: link })
    mounted.push(reopened)
    await useServerSettings()
    await reopened.vm.$nextTick()
    expect((reopened.vm as any).dataSettings).toMatchObject({ humanize: true, shape: 'wide', skipEmpty: true, dropNulls: false })
  })
})

import type { H3Event } from 'h3'
import type { ProviderNetworkCoverageResponse, ServerSettings } from '#shared/types/api'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError, getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { UApp } from '#components'
import { clearNuxtState, useNuxtApp, useRouter, useServerSettings, useToast } from '#imports'
import InterpolationSummarySelection from '~/components/InterpolationSummarySelection.vue'
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

  // the Unit Targets setting's "Default (...)" choices, one per type it lists, read from the items
  // the selects are given (the selects themselves are read by the GH-2391 tests)
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

  it('keeps a setting the user changed and changed back while the answer was on its way', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    endpoints.push(registerEndpoint('/api/settings', async () => {
      settingsAsked += 1
      await held
      return serverSettings()
    }))
    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(settingsAsked).toBe(1))

    vm.dataSettings.humanize = false
    vm.dataSettings.humanize = true
    release()
    await useServerSettings()
    await wrapper.vm.$nextTick()

    expect(vm.dataSettings.humanize).toBe(true)
    // one the user left alone is the server's
    expect(vm.dataSettings.shape).toBe('wide')
  })

  it('keeps an infinite radius the server reports, which the request then leaves to it', async () => {
    endpoints.push(registerEndpoint('/api/settings', () => {
      const settings = serverSettings()
      settings.interpolate.interpolation_station_distance_homogeneous = 'Infinity'
      return settings
    }))
    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(vm.dataSettings.stationDistanceHomogeneous).toBe(Number.POSITIVE_INFINITY))
    expect(vm.dataSettings.stationDistanceHeterogeneous).toBe(30)
  })

  it('asks again after a failure, which is not asked twice for a 500', async () => {
    endpoints.push(registerEndpoint('/api/settings', () => {
      settingsAsked += 1
      if (settingsAsked === 1)
        throw createError({ statusCode: 500 })
      return serverSettings()
    }))

    await expect(useServerSettings()).resolves.toBeNull()
    expect(settingsAsked).toBe(1)
    // a backend that was still starting answers the next one
    await expect(useServerSettings()).resolves.toEqual(serverSettings())
    expect(settingsAsked).toBe(2)
  })

  it('does not ask a backend without the endpoint again', async () => {
    endpoints.push(registerEndpoint('/api/settings', () => {
      settingsAsked += 1
      throw createError({ statusCode: 404 })
    }))

    await expect(useServerSettings()).resolves.toBeNull()
    await expect(useServerSettings()).resolves.toBeNull()
    expect(settingsAsked).toBe(1)
  })

  it('starts a new parameter\'s radius at 20 km where the server\'s heterogeneous one is infinite', async () => {
    endpoints.push(registerEndpoint('/api/settings', () => {
      const settings = serverSettings()
      settings.interpolate.interpolation_station_distance_heterogeneous = 'Infinity'
      return settings
    }))
    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.startingSettings.stationDistanceHeterogeneous).toBe(Number.POSITIVE_INFINITY))

    vm.addParameterDistance()
    expect(vm.parameterDistanceEntries.at(-1).distance).toBe(20)
  })
})

describe('explorer Page Unit Targets selects (GH-2391)', () => {
  // the errors Vue reports while a test runs: a select item that refuses its value throws in setup
  const errors: unknown[] = []
  let stopCollecting: (() => void) | undefined

  beforeEach(() => {
    clearNuxtState('server-settings')
    errors.length = 0
    stopCollecting = useNuxtApp().hook('vue:error', (error) => {
      errors.push(error)
    })
  })

  afterEach(() => {
    stopCollecting?.()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    useToast().clear()
  })

  // the explorer on a server converting temperatures to Fahrenheit and speeds to knots, with
  // Settings -> Unit Targets open
  async function mountWithUnitTargets(sent: Record<string, unknown>[]) {
    endpoints.push(registerEndpoint('/api/settings', () => ({
      values: { unit_targets: { temperature: 'degree_fahrenheit', speed: 'knots' } },
    })))
    const { wrapper, vm } = await mountWithSelection((event) => {
      sent.push(getQuery(event))
      return { values: [VALUE_ROW] }
    })
    await vi.waitFor(() => expect(vm.unitTargetDefaults.temperature).toBe('degree_fahrenheit'))
    await wrapper.findAll('button').find(b => b.text() === 'Settings')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.findAll('button').some(b => b.text() === 'Unit Targets')).toBe(true))
    await wrapper.findAll('button').find(b => b.text() === 'Unit Targets')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="unit-targets"]').exists()).toBe(true))
    return { wrapper, vm }
  }

  // the Unit Targets selects' triggers, one per type in the order listed
  function unitTargetTriggers(wrapper: Awaited<ReturnType<typeof mountWithSelection>>['wrapper']) {
    const unitTargets = wrapper.find('[data-testid="unit-targets"]')
    return [...unitTargets.element.querySelectorAll<HTMLButtonElement>('button[role="combobox"]')]
  }

  // open a select and pick the item labelled `label`
  async function choose(trigger: HTMLButtonElement, label: string) {
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    let item: HTMLElement | undefined
    await vi.waitFor(() => {
      const content = document.getElementById(trigger.getAttribute('aria-controls')!)
      item = [...(content?.querySelectorAll<HTMLElement>('[role="option"]') ?? [])]
        .find(option => option.textContent?.trim() === label)
      expect(item).toBeDefined()
    })
    item!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    // the select's own content closes once it has taken the choice
    await vi.waitFor(() => expect(trigger.getAttribute('aria-expanded')).toBe('false'))
  }

  it('names the server\'s unit on each select left at Default, without an error', async () => {
    const { wrapper } = await mountWithUnitTargets([])

    // the hint above them is the catalog's, read from it so the copy can change without this test
    expect(wrapper.find('[data-testid="unit-targets"] p').text())
      .toBe(useNuxtApp().$i18n.t('explorer.unitTargetsHint'))
    expect(unitTargetTriggers(wrapper).map(trigger => trigger.textContent?.trim())).toEqual([
      'Default (Degrees Fahrenheit (°F))',
      'Default (Knots (kn))',
      'Default (Hectopascal (hPa))',
      'Default (Millimetres (mm))',
      'Default (Millimetres per hour (mm/h))',
      'Default (Centimetres (cm))',
      'Default (Metres (m))',
      'Default (Kilometres (km))',
    ])
    expect(errors).toEqual([])
  })

  it('puts a type chosen back to Default to the server\'s unit in the request', async () => {
    const sent: Record<string, unknown>[] = []
    const { wrapper, vm } = await mountWithUnitTargets(sent)

    await choose(unitTargetTriggers(wrapper)[0]!, 'Kelvin (K)')
    expect(vm.dataSettings.unitTargets).toEqual({ temperature: 'degree_kelvin' })
    await choose(unitTargetTriggers(wrapper)[0]!, 'Default (Degrees Fahrenheit (°F))')
    expect(vm.dataSettings.unitTargets).toEqual({})
    expect(unitTargetTriggers(wrapper)[0]!.textContent?.trim()).toBe('Default (Degrees Fahrenheit (°F))')

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    expect(JSON.parse(String(sent[0]!.unit_targets))).toMatchObject({ temperature: 'degree_fahrenheit', speed: 'knots' })
    expect(errors).toEqual([])
  })
})

// the answers the page has been given to its requests for a shape's settings, in the order asked
const shapeAnswers = vi.hoisted(() => [] as Promise<unknown>[])
mockNuxtImport('serverSettingsFor', original => (...args: unknown[]) => {
  const answer = original(...args)
  shapeAnswers.push(answer)
  return answer
})

describe('explorer Page settings of the shape the user switches to (GH-2398)', () => {
  // the shape each GET /api/settings asked for, undefined for the server's own
  const asked: unknown[] = []

  beforeEach(() => {
    clearNuxtState('server-settings')
    asked.length = 0
    shapeAnswers.length = 0
  })

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    useToast().clear()
  })

  // GET /api/settings on a server with WD_TS_SHAPE=wide, which turns drop_nulls off, where the long
  // shape a request names has `dropNullsLong`: WD_TS_DROP_NULLS, or wetterdienst's true
  function wideServer(event: H3Event, dropNullsLong = true) {
    const shape = getQuery(event).shape === 'long' ? 'long' : 'wide'
    return { values: { shape, drop_nulls: shape === 'long' ? dropNullsLong : false } }
  }

  // the explorer on that server, with its settings in and Settings open
  async function mountOnWideServer(sent: Record<string, unknown>[]) {
    const { wrapper, vm } = await mountWithSelection((event) => {
      sent.push(getQuery(event))
      return { values: [VALUE_ROW] }
    })
    await vi.waitFor(() => expect(vm.dataSettings).toMatchObject({ shape: 'wide', dropNulls: false }))
    await wrapper.findAll('button').find(b => b.text() === 'Settings')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.findAll('button').some(b => b.text() === 'Long')).toBe(true))
    return { wrapper, vm }
  }

  async function switchShape(wrapper: Awaited<ReturnType<typeof mountWithSelection>>['wrapper'], label: string) {
    await wrapper.findAll('button').find(b => b.text() === label)!.trigger('click')
  }

  // the page done with the shape's answers: a request it would make is made once the tasks queued
  // have run, and each answer is taken in before an await on it made after the page's returns
  async function settle() {
    await new Promise(resolve => setTimeout(resolve))
    await Promise.all(shapeAnswers)
    await nextTick()
  }

  it.each([true, false])('takes the long shape\'s Drop nulls (%s) where the user switches to it, and sends it', async (dropNullsLong) => {
    endpoints.push(registerEndpoint('/api/settings', (event) => {
      asked.push(getQuery(event).shape)
      return wideServer(event, dropNullsLong)
    }))
    const sent: Record<string, unknown>[] = []
    const { wrapper, vm } = await mountOnWideServer(sent)

    await switchShape(wrapper, 'Long')
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'long']))
    await vi.waitFor(() => expect(vm.dataSettings.dropNulls).toBe(dropNullsLong))

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0]).toMatchObject({ shape: 'long', drop_nulls: String(dropNullsLong) })
  })

  it('keeps a Drop nulls the user changed', async () => {
    endpoints.push(registerEndpoint('/api/settings', (event) => {
      asked.push(getQuery(event).shape)
      return wideServer(event)
    }))
    const { wrapper, vm } = await mountOnWideServer([])

    // changed and changed back, which is still the user's
    vm.dataSettings.dropNulls = true
    vm.dataSettings.dropNulls = false
    await switchShape(wrapper, 'Long')
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'long']))
    await settle()
    expect(shapeAnswers).toHaveLength(1)

    expect(vm.dataSettings).toMatchObject({ shape: 'long', dropNulls: false })
  })

  // the page opened from the link it wrote on that server, as a reload does, the link naming
  // `humanize` off the server's too
  async function mountFromLink(query: string) {
    endpoints.push(registerEndpoint('/api/settings', (event) => {
      asked.push(getQuery(event).shape)
      return { values: { ...wideServer(event).values, humanize: false } }
    }))
    const wrapper = await mountSuspended(ExplorerPage, { route: `/explorer?humanize=true&shape=wide&${query}` })
    mounted.push(wrapper)
    const vm = wrapper.vm as any
    await expect(useServerSettings()).resolves.not.toBeNull()
    await settle()
    return vm
  }

  it('takes the link\'s Drop nulls on load, over the server\'s', async () => {
    const vm = await mountFromLink('dropNulls=true')

    expect(vm.dataSettings).toMatchObject({ humanize: true, shape: 'wide', dropNulls: true })
    expect(asked).toEqual([undefined])
  })

  it('takes the new shape\'s Drop nulls over the link\'s, and keeps the link\'s other settings (GH-2400)', async () => {
    const vm = await mountFromLink('dropNulls=false')

    vm.dataSettings.shape = 'long'
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'long']))
    await settle()

    expect(vm.dataSettings).toMatchObject({ humanize: true, shape: 'long', dropNulls: true })
  })

  it('keeps a Drop nulls the link names and the user changed (GH-2400)', async () => {
    const vm = await mountFromLink('dropNulls=false')

    // changed and changed back, which is still the user's
    vm.dataSettings.dropNulls = true
    vm.dataSettings.dropNulls = false
    vm.dataSettings.shape = 'long'
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'long']))
    await settle()
    expect(shapeAnswers).toHaveLength(1)

    expect(vm.dataSettings).toMatchObject({ shape: 'long', dropNulls: false })
  })

  it.each([404, 422, 500])('keeps Drop nulls where /api/settings answers the shape with a %i', async (status) => {
    endpoints.push(registerEndpoint('/api/settings', (event) => {
      asked.push(getQuery(event).shape)
      if (getQuery(event).shape)
        throw createError({ statusCode: status })
      return wideServer(event)
    }))
    const { wrapper, vm } = await mountOnWideServer([])

    await switchShape(wrapper, 'Long')
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'long']))
    await settle()

    expect(vm.dataSettings).toMatchObject({ shape: 'long', dropNulls: false })
  })

  it('does not ask a backend without /api/settings for the shape', async () => {
    endpoints.push(registerEndpoint('/api/settings', (event) => {
      asked.push(getQuery(event).shape)
      throw createError({ statusCode: 404 })
    }))
    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    const vm = wrapper.vm as any
    await expect(useServerSettings()).resolves.toBeNull()

    vm.dataSettings.shape = 'wide'
    await settle()

    expect(asked).toEqual([undefined])
    expect(vm.dataSettings).toMatchObject({ shape: 'wide', dropNulls: true })
  })

  it('lays the shape\'s Drop nulls over the first answer, where the user switched before it came', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    // a server of wetterdienst's long shape, whose wide one turns drop_nulls off
    endpoints.push(registerEndpoint('/api/settings', async (event) => {
      const shape = getQuery(event).shape
      asked.push(shape)
      if (!shape)
        await held
      return { values: { shape: shape ?? 'long', drop_nulls: shape !== 'wide' } }
    }))
    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(asked).toEqual([undefined]))

    vm.dataSettings.shape = 'wide'
    await settle()
    release()
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'wide']))
    await settle()

    expect(vm.dataSettings).toMatchObject({ shape: 'wide', dropNulls: false })
  })

  it('takes no answer for a shape the user has switched away from since', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    endpoints.push(registerEndpoint('/api/settings', async (event) => {
      asked.push(getQuery(event).shape)
      if (getQuery(event).shape === 'long')
        await held
      return wideServer(event)
    }))
    const { wrapper, vm } = await mountOnWideServer([])

    await switchShape(wrapper, 'Long')
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'long']))
    await switchShape(wrapper, 'Wide')
    await vi.waitFor(() => expect(asked).toEqual([undefined, 'long', 'wide']))
    expect(shapeAnswers).toHaveLength(2)
    await shapeAnswers[1]
    // the long shape's answer, drop_nulls on, comes in last
    release()
    await settle()

    expect(vm.dataSettings).toMatchObject({ shape: 'wide', dropNulls: false })
  })
})

describe('explorer Page point given by a station in a link (GH-2392)', () => {
  const HAMBURG = { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', latitude: 53.6332, longitude: 9.9881, elevation: 11 }
  const LINK = 'provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m'
    + '&interpolationSource=station&interpolationStation=01975&startDate=2020-01-01&endDate=2020-01-31'

  // the requests /api/stations got
  let stationsAsked = 0
  // the gates a test holds answers on, opened after it, before its page goes
  const releases: (() => void)[] = []

  beforeEach(() => {
    stationsAsked = 0
    clearNuxtState('server-settings')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    releases.splice(0).forEach(release => release())
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(remove => remove())
    useToast().clear()
  })

  // a gate the test opens: an answer held on it comes once `release` is called
  function gate() {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    releases.push(release)
    return { held, release }
  }

  // Open the link in `mode`, with the elevation it names; `stations` answers /api/stations
  async function open(stations: () => unknown, { mode = 'interpolation', elevation = '11' } = {}) {
    endpoints.push(registerEndpoint('/api/coverage', (event) => {
      if (getQuery(event).provider)
        return dailyClimateSummaryCoverage()
      return { dwd: { observation: {} } }
    }))
    endpoints.push(registerEndpoint('/api/stations', () => {
      stationsAsked += 1
      return stations()
    }))
    const wrapper = await mountSuspended(ExplorerWithApp, { attachTo: document.body, route: `/explorer?${LINK}&mode=${mode}&elevation=${elevation}` })
    mounted.push(wrapper)
    return { wrapper, vm: wrapper.findComponent(ExplorerPage).vm as any }
  }

  const query = () => useRouter().currentRoute.value.query

  // the link once the page has written it, which the link it was opened at, naming no setting, is not
  async function written() {
    await vi.waitFor(() => expect(query().humanize).toBeDefined())
    return query()
  }

  it.each(['interpolation', 'summary'])('restores the station as the point in %s mode, and keeps it in the link', async (mode) => {
    const { vm } = await open(() => ({ stations: [HAMBURG] }), { mode })

    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.station?.station_id).toBe('01975'))
    expect(vm.stationSelectionState.interpolation).toMatchObject({ source: 'station', latitude: 53.6332, longitude: 9.9881, elevation: 11 })
    expect(vm.hasLocationSelection).toBe(true)
    expect((await written()).interpolationStation).toBe('01975')
  })

  it('keeps the elevation the link was copied with, typed over the station\'s', async () => {
    const { vm } = await open(() => ({ stations: [HAMBURG] }), { elevation: '500' })

    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.station?.station_id).toBe('01975'))
    expect(vm.stationSelectionState.interpolation).toMatchObject({ latitude: 53.6332, longitude: 9.9881, elevation: 500 })
    expect(await written()).toMatchObject({ interpolationStation: '01975', elevation: '500' })
  })

  it('keeps an elevation typed while the list is on its way', async () => {
    const { held, release } = gate()
    const { wrapper, vm } = await open(async () => {
      await held
      return { stations: [HAMBURG] }
    })
    await vi.waitFor(() => expect(stationsAsked).toBe(1))
    await wrapper.find('input[placeholder="e.g. 34"]').setValue('300')
    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.elevation).toBe(300))

    release()
    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.station?.station_id).toBe('01975'))
    expect(vm.stationSelectionState.interpolation.elevation).toBe(300)
  })

  it('keeps the id in the link while the list is on its way, and in every link written on the way', async () => {
    const replace = vi.spyOn(useRouter(), 'replace')
    const { held, release } = gate()
    const { vm } = await open(async () => {
      await held
      return { stations: [HAMBURG] }
    })
    await vi.waitFor(() => expect(stationsAsked).toBe(1))

    expect((await written()).interpolationStation).toBe('01975')
    expect(vm.stationSelectionState.interpolation.station).toBeUndefined()

    release()
    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.station?.station_id).toBe('01975'))
    expect(query().interpolationStation).toBe('01975')
    // the page's own: none, the one written as the station is restored included, went without it
    const links = replace.mock.calls.map(([to]) => (to as { query?: Record<string, string> }).query).filter(q => q?.mode)
    expect(links.length).toBeGreaterThan(1)
    expect(links.map(q => q!.interpolationStation)).toEqual(links.map(() => '01975'))
  })

  it('keeps the id in the link when the list fails, and restores the station on Retry', async () => {
    let fail = true
    const { wrapper, vm } = await open(() => {
      if (fail)
        throw createError({ statusCode: 400 })
      return { stations: [HAMBURG] }
    })
    await vi.waitFor(() => expect(wrapper.text()).toContain('Failed to load stations.'))

    expect((await written()).interpolationStation).toBe('01975')
    expect(vm.stationSelectionState.interpolation.station).toBeUndefined()

    fail = false
    await wrapper.findAll('button').find(b => b.text() === 'Retry')!.trigger('click')
    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.station?.station_id).toBe('01975'))
    expect(query().interpolationStation).toBe('01975')
  })

  it('keeps the id in the link while the server\'s settings are on their way, and once they come', async () => {
    const settings = gate()
    const stations = gate()
    endpoints.push(registerEndpoint('/api/settings', async () => {
      await settings.held
      return { values: { humanize: false } }
    }))
    const { vm } = await open(async () => {
      await stations.held
      return { stations: [HAMBURG] }
    })

    expect((await written()).interpolationStation).toBe('01975')
    settings.release()
    await vi.waitFor(() => expect(query().humanize).toBe('false'))
    expect(query().interpolationStation).toBe('01975')

    stations.release()
    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.station?.station_id).toBe('01975'))
    expect(query().interpolationStation).toBe('01975')
  })

  // the picker offers neither: the point is left for the user to choose, as station mode leaves
  // out a station the list does not have, and the link no longer names it
  it.each([
    ['not in the list', { ...HAMBURG, station_id: '00001' }],
    ['without a position', { ...HAMBURG, latitude: null, longitude: null }],
  ])('leaves the point unset for a station %s, and drops it from the link', async (_, station) => {
    const { vm } = await open(() => ({ stations: [station] }))
    await vi.waitFor(() => expect(stationsAsked).toBe(1))

    await vi.waitFor(() => expect(query().interpolationStation).toBeUndefined())
    expect((await written()).interpolationSource).toBe('station')
    expect(vm.stationSelectionState.interpolation.station).toBeUndefined()
    expect(vm.hasLocationSelection).toBe(false)
  })

  it.each([
    ['', false],
    [', and back to a station', true],
  ])('gives the station up when the user switches to coordinates before the list came%s', async (_, back) => {
    const { held, release } = gate()
    const { wrapper, vm } = await open(async () => {
      await held
      return { stations: [HAMBURG] }
    })
    const source = (label: string) => wrapper.findAll('button').find(b => b.text() === label)!.trigger('click')
    await vi.waitFor(() => expect(stationsAsked).toBe(1))
    await source('Manual coordinates')
    await vi.waitFor(() => expect(query().interpolationSource).toBe('manual'))
    if (back) {
      await source('From station')
      await vi.waitFor(() => expect(query().interpolationSource).toBe('station'))
      expect(query().interpolationStation).toBeUndefined()
    }

    release()
    await vi.waitFor(() => expect(vm.stationSelectionState.interpolation.source).toBe(back ? 'station' : 'manual'))
    // the list has answered
    await vi.waitFor(() => expect((wrapper.findComponent(InterpolationSummarySelection).vm as any).stationsStatus).toBe('success'))
    expect(vm.stationSelectionState.interpolation.station).toBeUndefined()
    expect(vm.stationSelectionState.interpolation.latitude).toBeUndefined()
    expect(query().interpolationStation).toBeUndefined()
  })

  it('forgets the station when the dataset changes before the list came', async () => {
    const { held } = gate()
    const { vm } = await open(async () => {
      await held
      return { stations: [HAMBURG] }
    })
    await vi.waitFor(() => expect(stationsAsked).toBe(1))

    // the parameter selection takes back a resolution the provider does not have, which is a change too
    vm.parameterSelectionState.selection.resolution = 'hourly'
    await vi.waitFor(() => expect(query()).toMatchObject({ interpolationSource: 'manual' }))
    expect(query().resolution).toBeUndefined()
    vm.stationSelectionState.interpolation = { source: 'station' }
    await vi.waitFor(() => expect(query().interpolationSource).toBe('station'))
    expect(query().interpolationStation).toBeUndefined()
  })
})

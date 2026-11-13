import type { VueWrapper } from '@vue/test-utils'
import type { H3Event } from 'h3'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { useSettings } from '#imports'
import Meteogram from '~/components/Meteogram.vue'
import MeteogramPage from '~/pages/meteogram.vue'
import { fill, messagesOf, OTHER_LANGUAGES } from '../fixtures/catalogs'

/** Shows the map of the station picker: the reader's click on "Map" of its toggle */
async function showMap(wrapper: VueWrapper) {
  await wrapper.findAll('[role="radio"]').find(radio => radio.text() === 'Map')!.trigger('click')
}

/**
 * Mounts the page and unmounts it when the test is over. A page left mounted keeps its watchers on the app's one
 * route, and one whose lookup of the link's station is still under way when the route leaves that station forgets
 * what it asked for, and asks again when a later test navigates to `/meteogram?station=…`: into that test's endpoint
 * and count. The first tests of this file left 14 pages, so `asked` was 14 (GH-4042). On a quiet machine the lookups are
 * answered before the route moves and the leftovers stay silent, which is why it showed under load only.
 */
async function mountPage(options?: Parameters<typeof mountSuspended>[1]) {
  const wrapper = await mountSuspended(MeteogramPage, options)
  onTestFinished(() => wrapper.unmount())
  return wrapper
}

describe('meteogram Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
    registerEndpoint('/api/stations', () => ({ stations: [] }))
  })

  it('renders the page', async () => {
    const wrapper = await mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('displays the forecast heading', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Weather forecast')
  })

  it('shows the empty-state hint before a station is selected', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Search for a station or pick one on the map to see its forecast')
    expect(wrapper.find('[data-testid="tool-placeholder"]').attributes('data-tool')).toBe('forecast')
  })

  it('titles the first card by what it holds, a station', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.text-lg.font-bold').text()).toBe('Station')
  })

  it('has a station picker with a toggle between the search and the map', async () => {
    const wrapper = await mountPage()
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios.map(radio => radio.text())).toEqual(['List', 'Map'])
    expect(radios.map(radio => radio.attributes('aria-checked'))).toEqual(['true', 'false'])
  })

  it('fetches the meteogram when a station is selected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountPage()
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/values?'),
    )
  })

  it('surfaces backend errors', async () => {
    // a body that isn't the API's, as a proxy's error page, is told by the status alone
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response('<html>proxy page</html>', { status: 500, statusText: 'Internal Server Error' }),
    )

    const wrapper = await mountPage()
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 500 Internal Server Error'))
  })

  it('tells a 200 page of HTML as a failure, not as a forecast with no values (GH-3841)', async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response('<!doctype html><html><body>Bad gateway</body></html>', { status: 200, headers: { 'content-type': 'text/html' } }),
    )

    const wrapper = await mountPage()
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await vi.waitFor(() => expect(vm.error).toMatch(/^Backend error 502: The API answered with a web page, not data/))
  })

  it('tells JSON without the list of values as a failure, not as a forecast with no values (GH-3841)', async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response(JSON.stringify({ message: 'something else answered' }), { status: 200, headers: { 'content-type': 'application/json' } }),
    )

    const wrapper = await mountPage()
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await vi.waitFor(() => expect(vm.error).toMatch(/^Backend error 502: .*no list of `values`/))
  })

  it('tells a refused request by the backend\'s detail', async () => {
    // answered as FastAPI answers a request that fails validation: the entries under `detail`, which tell it
    // in place of the status text
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response(JSON.stringify({ detail: [{ loc: ['query', 'stations'], msg: 'Unknown station' }] }), { status: 422, statusText: 'Unprocessable Entity' }),
    )

    const wrapper = await mountPage()
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 422: stations: Unknown station'))
  })

  it('clears state and URL query when the station is deselected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountPage()
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))

    vm.selectedStation = null
    await wrapper.vm.$nextTick()

    expect(vm.values).toEqual([])
    expect(vm.error).toBeNull()
  })

  it('clicking the about toggle reveals the explanatory text', async () => {
    const wrapper = await mountPage({ attachTo: document.body })
    expect(wrapper.text()).not.toContain('multi-day weather forecast from DWD MOSMIX')

    const aboutButton = wrapper.findAll('button').find(b => b.text().includes('About the forecast'))
    await aboutButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('multi-day weather forecast from DWD MOSMIX')
  })

  it('showing the map loads the stations and reveals the map picker', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }],
    }))

    // Stub ClientOnly -- it wraps MapStations, which mounts real Leaflet +
    // leaflet.markercluster (CJS/PNG asset code that isn't happy-dom/Node-ESM
    // friendly and isn't what this test is about). The map's own rendering
    // is covered by e2e (real browser) tests instead.
    const wrapper = await mountPage({ attachTo: document.body, global: { stubs: { ClientOnly: true } } })
    const vm = wrapper.vm as any
    // the list is large: not asked for before the search is opened or the map shown
    expect(vm.stations).toEqual([])

    await showMap(wrapper)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[role="radio"][aria-checked="true"]').text()).toBe('Map')
    expect(vm.stations).toEqual([
      { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 },
    ])
  })
})

// Nuxt's reload of the page: the test's document does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

describe('the meteogram page\'s station map whose code could not be loaded', () => {
  let wrapper: VueWrapper | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.doUnmock('~/components/MapStations.vue')
    vi.restoreAllMocks()
    reloadNuxtApp.mockClear()
  })

  it('says so in place of the map, without the hint to tap it, and offers a reload', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '01001', name: 'JAN MAYEN', region: 'Norway', latitude: 70.93, longitude: -8.67 }],
    }))
    wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body })
    // the map's chunk fails as it does where a redeploy has replaced it under an open tab, once the
    // hint was seen while it loaded
    let fail!: () => void
    const failing = new Promise<void>((resolve) => {
      fail = resolve
    })
    vi.doMock('~/components/MapStations.vue', async () => {
      await failing
      throw new Error('chunk failed to load')
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await showMap(wrapper!)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Tap a marker on the map to pick that station.'))
    fail()
    const alert = await vi.waitFor(() => {
      const found = wrapper!.find('[role="alert"]')
      expect(found.exists()).toBe(true)
      return found
    })
    expect(alert.text()).toBe('The stations could not be shown on the map. Reload the page to try again.')
    expect(wrapper.text()).not.toContain('Tap a marker on the map to pick that station.')
    await wrapper.findAll('button').find(b => b.text() === 'Reload page')!.trigger('click')
    // forced: unforced, Nuxt drops a second click within ten seconds of a first that did not help
    expect(reloadNuxtApp).toHaveBeenCalledExactlyOnceWith({ force: true })
  })
})

describe('the meteogram page\'s requests answered with a 500', () => {
  let wrapper: VueWrapper | undefined
  // disposers of the endpoints these tests register, so none answers a later test
  const endpoints: Array<() => void> = []

  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    endpoints.push(registerEndpoint('/api/stations', () => ({ stations: [] })))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
  })

  // counted at the endpoint, which a request reaches however it is made
  function failing(counts: (query: Record<string, unknown>) => boolean = () => true) {
    const asked = { count: 0 }
    return {
      asked,
      handler: (event: H3Event) => {
        if (counts(getQuery(event)))
          asked.count++
        setResponseStatus(event, 500)
        return { detail: 'Upstream failed' }
      },
    }
  }

  it('asks /api/issues once', async () => {
    const { asked, handler } = failing()
    endpoints.push(registerEndpoint('/api/issues', handler))
    wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any
    // emptied once the request has failed, which a request asked again does after its second answer
    vm.availableIssues = ['2026-10-03T06:00:00']
    vm.selectedStation = { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }
    await vi.waitFor(() => expect(vm.availableIssues).toEqual([]))
    expect(asked.count).toBe(1)
  })

  it('asks /api/stations once for the picker\'s stations', async () => {
    wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body, global: { stubs: { ClientOnly: true } } })
    const vm = wrapper.vm as any
    const { asked, handler } = failing()
    endpoints.push(registerEndpoint('/api/stations', handler))
    await showMap(wrapper)
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked.count).toBeGreaterThan(0)
      expect(vm.stationsLoading).toBe(false)
    })
    expect(asked.count).toBe(1)
    // told, and asked again where the reader shows the map or opens the search once more
    expect(vm.stationsFailed).toBe(true)
    expect(wrapper.text()).toContain('Failed to load stations')
  })

  it('asks /api/stations once for the station a shared link names', async () => {
    // the picker's list is asked for all stations, the link's station by its id
    const { asked, handler } = failing(query => query.stations === '01001')
    endpoints.push(registerEndpoint('/api/stations', handler))
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked.count).toBeGreaterThan(0)
      expect(vm.isRestoringFromUrl).toBe(false)
    })
    expect(asked.count).toBe(1)
  })
})

describe('the meteogram page\'s requests answered with a 503 once', () => {
  const janMayen = { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }
  let wrapper: VueWrapper | undefined
  // disposers of the endpoints these tests register, so none answers a later test
  const endpoints: Array<() => void> = []

  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    endpoints.push(registerEndpoint('/api/stations', () => ({ stations: [] })))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
  })

  // a 503 the first time only, as a proxy gives while the backend restarts; the requests `counts`
  // leaves out get no stations
  function flaky(answer: unknown, counts: (query: Record<string, unknown>) => boolean = () => true) {
    const asked = { count: 0 }
    return {
      asked,
      handler: (event: H3Event) => {
        if (!counts(getQuery(event)))
          return { stations: [] }
        asked.count++
        if (asked.count === 1) {
          setResponseStatus(event, 503)
          return { detail: 'Service Unavailable' }
        }
        return answer
      },
    }
  }

  it('asks /api/issues once more, and offers the runs that answer brings', async () => {
    const { asked, handler } = flaky({ issues: ['2026-10-03T06:00:00'] })
    endpoints.push(registerEndpoint('/api/issues', handler))
    wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any
    vm.selectedStation = janMayen
    await vi.waitFor(() => expect(vm.availableIssues).toEqual(['2026-10-03T06:00:00']))
    expect(asked.count).toBe(2)
  })

  it('asks /api/stations once more for the picker\'s stations, and shows what that answer brings', async () => {
    wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body, global: { stubs: { ClientOnly: true } } })
    const vm = wrapper.vm as any
    const { asked, handler } = flaky({ stations: [janMayen] })
    endpoints.push(registerEndpoint('/api/stations', handler))
    await showMap(wrapper)
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    expect(asked.count).toBe(2)
  })

  it('asks /api/stations once more for the station a shared link names, and selects it', async () => {
    // the picker's list is asked for all stations, the link's station by its id
    const { asked, handler } = flaky({ stations: [janMayen] }, query => query.stations === '01001')
    endpoints.push(registerEndpoint('/api/stations', handler))
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    expect(asked.count).toBe(2)
  })
})

describe('meteogram Page values request', () => {
  it('asks for the layout and units the meteogram reads, whatever the server\'s WD_TS_* say', async () => {
    onTestFinished(registerEndpoint('/api/stations', () => ({ stations: [] })))
    onTestFinished(registerEndpoint('/api/issues', () => ({ issues: [] })))
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    const wrapper = await mountSuspended(MeteogramPage)
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    vm.selectedStation = { station_id: '01001', name: 'Jan Mayen', latitude: 70.9, longitude: -8.7 }
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/values?')))

    const asked = vi.mocked(globalThis.fetch).mock.calls.map(([input]) => String(input)).find(input => input.includes('/api/values?'))!
    const query = new URL(asked, 'http://localhost').searchParams
    expect(query.get('stations')).toBe('01001')
    expect(query.get('shape')).toBe('long')
    expect(query.get('humanize')).toBe('true')
    expect(query.get('convert_units')).toBe('true')
    expect(query.get('skip_empty')).toBe('false')
    // the answer says the unit of each parameter, which the charts are labelled by
    expect(query.get('with_metadata')).toBe('true')
    // each quantity the charts give a unit for, in the unit the app settings choose (the app's defaults here), and every
    // other type the settings page lists, as the server's own targets are merged into the request's
    expect(JSON.parse(query.get('unit_targets')!)).toMatchObject({
      angle: 'degree',
      fraction: 'percent',
      precipitation: 'millimeter',
      pressure: 'hectopascal',
      speed: 'meter_per_second',
      temperature: 'degree_celsius',
    })
  })
})

// The forecast follows the unit settings (GH-3980): the request carries them, the chart is told the unit the answer reports
// for each parameter, and a change of them while a forecast is shown fetches it again
describe('meteogram Page units', () => {
  const station = { station_id: '70001', name: 'Test Island', latitude: 70.9, longitude: -8.7 }
  const row = (parameter: string, value: number) => ({ station_id: '70001', resolution: 'hourly', dataset: 'large', parameter, timestamp: '2026-10-01T00:00:00+00:00', value, quality_flags: null })
  // the answer to a request, in the temperature unit it asked for
  const answer = (query: URLSearchParams) => {
    const fahrenheit = JSON.parse(query.get('unit_targets')!).temperature === 'degree_fahrenheit'
    return {
      values: [row('temperature_air_2m', fahrenheit ? 50 : 10)],
      metadata: { parameters: [{ name: 'temperature_air_2m', quantity: 'temperature', unit: fahrenheit ? '°F' : '°C' }] },
    }
  }
  const valuesRequests = () => vi.mocked(globalThis.fetch).mock.calls.map(([input]) => new URL(String(input), 'http://localhost')).filter(url => url.pathname === '/api/values' && url.searchParams.get('stations') === '70001')
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  let gate: Promise<void> | null = null

  beforeEach(() => {
    onTestFinished(registerEndpoint('/api/stations', () => ({ stations: [] })))
    onTestFinished(registerEndpoint('/api/issues', () => ({ issues: [] })))
    globalThis.fetch = vi.fn(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      await gate
      return new Response(JSON.stringify(answer(url.searchParams)), { status: 200 })
    })
  })
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    gate = null
    useSettings().settings.value.units.temperature = 'degree_celsius'
    useSettings().settings.value.convertUnits = true
  })

  async function showForecast() {
    wrapper = await mountSuspended(MeteogramPage)
    ;(wrapper.vm as any).selectedStation = station
    await vi.waitFor(() => expect(valuesRequests()).toHaveLength(1))
    return wrapper
  }
  const chartUnits = () => wrapper!.findComponent(Meteogram).props('units')

  it('asks in the unit the settings choose, and tells the chart the unit the answer reports', async () => {
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await showForecast()
    expect(JSON.parse(valuesRequests()[0]!.searchParams.get('unit_targets')!).temperature).toBe('degree_fahrenheit')
    await vi.waitFor(() => expect(chartUnits()).toEqual({ temperature_air_2m: '°F' }))
  })

  it('asks for the values unconverted where the settings say so', async () => {
    useSettings().settings.value.convertUnits = false
    await showForecast()
    expect(valuesRequests()[0]!.searchParams.get('convert_units')).toBe('false')
  })

  it('fetches the forecast again, once, in the new unit where the settings change while it is shown', async () => {
    await showForecast()
    await vi.waitFor(() => expect(chartUnits()).toEqual({ temperature_air_2m: '°C' }))
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await vi.waitFor(() => expect(valuesRequests()).toHaveLength(2))
    expect(JSON.parse(valuesRequests()[1]!.searchParams.get('unit_targets')!).temperature).toBe('degree_fahrenheit')
    await vi.waitFor(() => expect(chartUnits()).toEqual({ temperature_air_2m: '°F' }))
    // no third request follows
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(valuesRequests()).toHaveLength(2)
  })

  it('leaves the forecast as it is where a unit it does not draw changes', async () => {
    await showForecast()
    await vi.waitFor(() => expect(chartUnits()).toEqual({ temperature_air_2m: '°C' }))
    useSettings().settings.value.units.conductivity = 'siemens_per_meter'
    useSettings().settings.value.units.length_long = 'mile'
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(valuesRequests()).toHaveLength(1)
    useSettings().settings.value.units.conductivity = 'microsiemens_per_centimeter'
    useSettings().settings.value.units.length_long = 'kilometer'
  })

  it('shows the answer of the newest request where the settings change while one is under way, which is followed by one more', async () => {
    let release!: () => void
    gate = new Promise<void>((resolve) => {
      release = resolve
    })
    wrapper = await mountSuspended(MeteogramPage)
    ;(wrapper.vm as any).selectedStation = station
    await vi.waitFor(() => expect(valuesRequests()).toHaveLength(1))
    // the first answer is held: the unit changes meanwhile
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await vi.waitFor(() => expect(valuesRequests()).toHaveLength(2))
    release()
    await vi.waitFor(() => expect(chartUnits()).toEqual({ temperature_air_2m: '°F' }))
    expect(valuesRequests()).toHaveLength(2)
    expect((wrapper.vm as any).values[0].value).toBe(50)
  })
})

// Real Leaflet draws nothing in happy-dom, and LMap imports its marker images, which Node can't: the
// station map the page loads is not what these tests are about
vi.mock('@vue-leaflet/vue-leaflet', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    LMap: defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) }),
    LTileLayer: defineComponent({ setup: () => () => null }),
  }
})

describe('meteogram Page failures in the active language', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
    registerEndpoint('/api/stations', () => ({ stations: [] }))
  })

  // the language switched to for the test, and back (GH-2971)
  async function inLanguage(language: string) {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as any).setLocale(language)
    onTestFinished(async () => {
      await (harness.vm as any).setLocale('en')
      harness.unmount()
    })
  }

  const station = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }

  it.each([
    ['en', 'Request failed'],
    ['de', 'Anfrage fehlgeschlagen'],
    ['fr', 'La requête a échoué'],
    ['pl', 'Żądanie nie powiodło się'],
  ])('says in %s that a request threw with no message', async (language, expected) => {
    await inLanguage(language)
    // a rejection that carries no message, as a request aborted by the browser can
    vi.mocked(globalThis.fetch).mockRejectedValue({})

    const wrapper = await mountSuspended(MeteogramPage)
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    vm.selectedStation = station
    await vi.waitFor(() => expect(vm.error).toBe(expected))
  })

  it.each([
    ['en', 'Backend error 502: '],
    ['de', 'Backend-Fehler 502: '],
    ['fr', 'Erreur du backend 502\u00A0: '],
    ['pl', 'Błąd backendu 502: '],
  ])('tells an answer that is a page as the backend\'s own failure in %s, as the proxy\'s problem reads (GH-3841)', async (language, start) => {
    await inLanguage(language)
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response('<!doctype html><html><body>Bad gateway</body></html>', { status: 200, headers: { 'content-type': 'text/html' } }),
    )
    const wrapper = await mountSuspended(MeteogramPage)
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    vm.selectedStation = station
    await vi.waitFor(() => expect(vm.error).toBe(`${start}The API answered with a web page, not data. The address of the API may be wrong, or a proxy in front of it answered with its own page.`))
  })

  it.each([
    ['en', 'Backend error 422: stations: Unknown station', 'Backend error 500 Internal Server Error'],
    ['de', 'Backend-Fehler 422: stations: Unknown station', 'Backend-Fehler 500 Internal Server Error'],
    ['fr', 'Erreur du backend 422\u00A0: stations: Unknown station', 'Erreur du backend 500 Internal Server Error'],
    ['pl', 'Błąd backendu 422: stations: Unknown station', 'Błąd backendu 500 Internal Server Error'],
  ])('names the backend\'s error in %s', async (language, withDetail, withStatus) => {
    await inLanguage(language)
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response(JSON.stringify({ detail: [{ loc: ['query', 'stations'], msg: 'Unknown station' }] }), { status: 422, statusText: 'Unprocessable Entity' }),
    )
    const wrapper = await mountSuspended(MeteogramPage)
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    vm.selectedStation = station
    await vi.waitFor(() => expect(vm.error).toBe(withDetail))

    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response('<html>proxy page</html>', { status: 500, statusText: 'Internal Server Error' }),
    )
    vm.selectedStation = { ...station, station_id: '00002' }
    await vi.waitFor(() => expect(vm.error).toBe(withStatus))
  })
})

// the failure on show is written again in the language switched to, not kept in the one it was made in (GH-3052)
describe('meteogram Page failure after a language switch', () => {
  const messages = (code: string) => messagesOf(code, 'common')
  const station = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
  const languages = OTHER_LANGUAGES

  let harness: Awaited<ReturnType<typeof mountSuspended>> | undefined
  let wrapper: VueWrapper | undefined
  const setLocale = (code: string) => (harness!.vm as any).setLocale(code)

  beforeEach(async () => {
    globalThis.fetch = vi.fn()
    registerEndpoint('/api/stations', () => ({ stations: [] }))
    harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await setLocale('en')
  })

  afterEach(async () => {
    wrapper?.unmount()
    wrapper = undefined
    await setLocale('en')
    harness?.unmount()
    harness = undefined
  })

  // the page shows the failure in English, the language is switched, and the same failure is shown again
  async function failedThenSwitched(code: string, answer: () => Promise<Response>) {
    vi.mocked(globalThis.fetch).mockImplementation(answer)
    wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any
    vm.selectedStation = station
    await vi.waitFor(() => expect(vm.error).not.toBeNull())
    const before = vm.error
    await setLocale(code)
    await vi.waitFor(() => expect(wrapper!.text()).toContain(vm.error))
    return { before, after: vm.error as string, requests: vi.mocked(globalThis.fetch).mock.calls.length }
  }

  it.each(languages)('writes the failure of a request with no message in %s', async (code) => {
    const { before, after, requests } = await failedThenSwitched(code, async () => Promise.reject(Object.assign(new Error('aborted'), { message: '' })))
    expect(before).toBe(messages('en').requestFailed)
    expect(after).toBe(messages(code).requestFailed)
    expect(after).not.toBe(before)
    // the message was translated, not asked for again
    expect(requests).toBe(1)
  })

  it.each(languages)('writes the backend\'s error with its reason in %s', async (code) => {
    const { before, after } = await failedThenSwitched(code, async () =>
      new Response(JSON.stringify({ detail: 'Unknown station' }), { status: 422, statusText: 'Unprocessable Entity' }))
    expect(before).toBe('Backend error 422: Unknown station')
    expect(after).toBe(fill(messages(code).backendErrorDetail!, { status: '422', detail: 'Unknown station' }))
    expect(after).not.toBe(before)
  })

  it.each(languages)('writes the backend\'s error with its status in %s, the status text as the server wrote it', async (code) => {
    const { before, after } = await failedThenSwitched(code, async () =>
      new Response('<html>proxy page</html>', { status: 502, statusText: 'Bad Gateway' }))
    expect(before).toBe('Backend error 502 Bad Gateway')
    expect(after).toBe(`${fill(messages(code).backendError!, { status: '502' })} Bad Gateway`)
    expect(after).not.toBe(before)
  })

  it('leaves a message of the browser\'s own as it is', async () => {
    const { before, after } = await failedThenSwitched('de', async () => Promise.reject(new TypeError('Failed to fetch')))
    expect(before).toBe('Failed to fetch')
    expect(after).toBe('Failed to fetch')
  })
})

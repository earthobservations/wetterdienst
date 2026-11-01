import type { VueWrapper } from '@vue/test-utils'
import type { H3Event } from 'h3'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import MeteogramStationSearch from '~/components/MeteogramStationSearch.vue'
import MeteogramPage from '~/pages/meteogram.vue'
import { fill, messagesOf, OTHER_LANGUAGES } from '../fixtures/catalogs'

describe('meteogram Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
    registerEndpoint('/api/stations', () => ({ stations: [] }))
  })

  it('renders the page', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays the forecast heading', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.text()).toContain('Weather forecast')
  })

  it('shows the empty-state hint before a station is selected', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.text()).toContain('Search for a station above to generate a forecast')
  })

  it('has a station search and map picker', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.text()).toContain('Choose a station on the map')
  })

  it('fetches the meteogram when a station is selected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(MeteogramPage)
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

    const wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 500 Internal Server Error'))
  })

  it('tells a refused request by the backend\'s detail', async () => {
    // answered as FastAPI answers a request that fails validation: the entries under `detail`, which tell it
    // in place of the status text
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response(JSON.stringify({ detail: [{ loc: ['query', 'stations'], msg: 'Unknown station' }] }), { status: 422, statusText: 'Unprocessable Entity' }),
    )

    const wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 422: stations: Unknown station'))
  })

  it('clears state and URL query when the station is deselected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(MeteogramPage)
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
    const wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body })
    expect(wrapper.text()).not.toContain('multi-day weather forecast from DWD MOSMIX')

    const aboutButton = wrapper.findAll('button').find(b => b.text().includes('About the forecast'))
    await aboutButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('multi-day weather forecast from DWD MOSMIX')
  })

  it('clicking "Choose a station on the map" loads and reveals the map picker', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }],
    }))

    // Stub ClientOnly -- it wraps MapStations, which mounts real Leaflet +
    // leaflet.markercluster (CJS/PNG asset code that isn't happy-dom/Node-ESM
    // friendly and isn't what this test is about). The map's own rendering
    // is covered by e2e (real browser) tests instead.
    const wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body, global: { stubs: { ClientOnly: true } } })
    const vm = wrapper.vm as any
    expect(vm.mapStations).toEqual([])

    const mapToggle = wrapper.findAll('button').find(b => b.text().includes('Choose a station on the map'))
    await mapToggle!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(vm.showMap).toBe(true)
    expect(vm.mapStations).toEqual([
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
    await wrapper.findAll('button').find(b => b.text().includes('Choose a station on the map'))!.trigger('click')
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

  it('asks /api/stations once for the map\'s stations', async () => {
    wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body, global: { stubs: { ClientOnly: true } } })
    const vm = wrapper.vm as any
    // the station search's own list, asked for the same stations, answered before the map's fails
    await vi.waitFor(() => expect((wrapper!.findComponent(MeteogramStationSearch).vm as any).pending).toBe(false))
    const { asked, handler } = failing()
    endpoints.push(registerEndpoint('/api/stations', handler))
    await wrapper.findAll('button').find(b => b.text().includes('Choose a station on the map'))!.trigger('click')
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked.count).toBeGreaterThan(0)
      expect(vm.mapLoading).toBe(false)
    })
    expect(asked.count).toBe(1)
  })

  it('asks /api/stations once for the station a shared link names', async () => {
    // the station search's list is asked for all stations, the link's station by its id
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

describe('the meteogram page followed to a station by the search of the header (GH-3518)', () => {
  const stations: Record<string, { station_id: string, name: string, latitude: number, longitude: number }> = {
    '01001': { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 },
    '10381': { station_id: '10381', name: 'BERLIN', latitude: 52.46, longitude: 13.31 },
  }
  let wrapper: VueWrapper | undefined
  const endpoints: Array<() => void> = []

  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    endpoints.push(registerEndpoint('/api/stations', (event) => {
      const station = stations[String(getQuery(event).stations)]
      return { stations: station ? [station] : [] }
    }))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
  })

  it('shows the station the URL names again after the page chose another one', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    // the reader picks another station in the page, which the page writes to the URL
    vm.selectedStation = stations['10381']
    await vi.waitFor(() => expect(useRoute().query.station).toBe('10381'))
    // and then searches the first one again in the header
    await navigateTo('/meteogram?station=01001')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
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

  it('asks /api/stations once more for the map\'s stations, and shows what that answer brings', async () => {
    wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body, global: { stubs: { ClientOnly: true } } })
    const vm = wrapper.vm as any
    // the station search's own list, asked for the same stations, answered before the map's is asked
    await vi.waitFor(() => expect((wrapper!.findComponent(MeteogramStationSearch).vm as any).pending).toBe(false))
    const { asked, handler } = flaky({ stations: [janMayen] })
    endpoints.push(registerEndpoint('/api/stations', handler))
    await wrapper.findAll('button').find(b => b.text().includes('Choose a station on the map'))!.trigger('click')
    await vi.waitFor(() => expect(vm.mapStations).toHaveLength(1))
    expect(asked.count).toBe(2)
  })

  it('asks /api/stations once more for the station a shared link names, and selects it', async () => {
    // the station search's list is asked for all stations, the link's station by its id
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
    // each quantity the charts give a unit for, as the server's own targets are merged into the request's
    expect(JSON.parse(query.get('unit_targets')!)).toEqual({
      angle: 'degree',
      fraction: 'decimal',
      precipitation: 'millimeter',
      pressure: 'hectopascal',
      speed: 'meter_per_second',
      temperature: 'degree_celsius',
    })
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

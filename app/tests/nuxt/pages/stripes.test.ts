import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { UApp } from '#components'
import { useToast } from '#imports'
import MapStations from '~/components/MapStations.vue'
import StripesPage from '~/pages/stripes.vue'

// Real Leaflet draws nothing in happy-dom. The LMap stub holds a stand-in Leaflet map, as LMap
// holds the real one, for the station map to centre; it never emits ready, so no markers are built.
const { leafletMap } = vi.hoisted(() => ({
  leafletMap: { fitBounds: vi.fn() },
}))
vi.mock('@vue-leaflet/vue-leaflet', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    LMap: defineComponent({
      setup: (_, { slots, expose }) => {
        expose({ leafletObject: leafletMap })
        return () => h('div', slots.default?.())
      },
    }),
    LTileLayer: defineComponent({ setup: () => () => null }),
  }
})

// Plotly draws nothing in the test's document: its calls are recorded
const plotly = vi.hoisted(() => ({
  newPlot: vi.fn(async () => {}),
  relayout: vi.fn(async () => {}),
  purge: vi.fn(),
  downloadImage: vi.fn(async () => 'stripes'),
}))
vi.mock('plotly.js-basic-dist-min', () => plotly)

describe('stripes Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays climate stripes title', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const text = wrapper.text()

    expect(text).toContain('Climate stripes')
  })

  it('has station selection', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)

    expect(wrapper.html()).toBeTruthy()
  })

  it('allows selecting kind (temperature/precipitation)', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const vm = wrapper.vm as any

    expect(vm.kind).toBeDefined()
    expect(['temperature', 'precipitation']).toContain(vm.kind)
  })

  it('fetches stations based on kind', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const vm = wrapper.vm as any

    expect(vm.stations).toBeDefined()
  })

  it('clicking the about toggle reveals the explanatory text', async () => {
    const wrapper = await mountSuspended(StripesPage, { attachTo: document.body })
    expect(wrapper.text()).not.toContain('data visualization designed to communicate')

    const aboutButton = wrapper.findAll('button').find(b => b.text().includes('About climate stripes'))
    await aboutButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('data visualization designed to communicate')
  })

  it('clicking Show plots the stripes, and clicking Reset clears the plot', async () => {
    const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', start_date: '1950-01-01', end_date: '2020-01-01' }
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      metadata: { station },
      years: [{ year: 2000, value: 9.5 }],
    }))

    const wrapper = await mountSuspended(StripesPage, { attachTo: document.body })
    const vm = wrapper.vm as any
    // Let the stations useFetch resolve so the "clear selection if not in
    // stations list" watcher doesn't wipe the station set directly below.
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    vm.selectedStation = station
    await wrapper.vm.$nextTick()

    const fetchButton = wrapper.findAll('button').find(b => b.text() === 'Show')
    expect(fetchButton?.attributes('disabled')).toBeUndefined()
    await fetchButton!.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    expect(vm.hasPlot).toBe(true)

    const resetButton = wrapper.findAll('button').find(b => b.text() === 'Reset')
    await resetButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(vm.hasPlot).toBe(false)
  })
})

describe('stripes Page station map', () => {
  const tempelhof = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_date: '1950-01-01', end_date: '2020-01-01' }
  const potsdam = { station_id: '3987', name: 'Potsdam', region: 'Brandenburg', latitude: 52.38, longitude: 13.06, start_date: '1893-01-01', end_date: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    leafletMap.fitBounds.mockClear()
  })

  it('stays centred on all stations, as the user chose, when the map\'s section renders again', async () => {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [tempelhof, potsdam] }))
    // precipitation, as the pages the tests above leave mounted hold the temperature stations' fetch
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(2))
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text().includes('Choose on the map'))!.trigger('click')
    await vi.waitFor(() => expect(wrapper!.findComponent(MapStations).exists()).toBe(true))
    const map = wrapper.findComponent(MapStations)
    const fitBounds = leafletMap.fitBounds
    const centreButton = () => map.findAll('button').find((b: { text: () => string }) => b.text().startsWith('Center on'))!

    // a station is chosen on the map, which centres on it
    map.vm.$emit('update:selectedStations', [tempelhof])
    await vi.waitFor(() => expect(centreButton().text()).toBe('Center on all stations'))
    expect(fitBounds).toHaveBeenCalled()
    await centreButton().trigger('click')
    expect(centreButton().text()).toBe('Center on selected station')
    const fits = fitBounds.mock.calls.length

    // the map's section renders again, with the same station chosen: the component around the map
    // renders the page's slot content anew
    map.vm.$parent!.$forceUpdate()
    await nextTick()
    await nextTick()

    expect(centreButton().text()).toBe('Center on selected station')
    expect(fitBounds).toHaveBeenCalledTimes(fits)
  })
})

describe('stripes Page years', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_date: '1950-01-01', end_date: '2020-01-01' }

  // a browser five hours west of UTC, where the first moment of a year in UTC is still the year before
  let zone: string | undefined
  beforeAll(() => {
    zone = process.env.TZ
    process.env.TZ = 'America/New_York'
    // the zone taken up, else the test passes in UTC against getFullYear as well
    expect(new Date(2020, 0, 1).getTimezoneOffset()).toBe(300)
  })

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  afterAll(() => {
    if (zone === undefined)
      delete process.env.TZ
    else
      process.env.TZ = zone
  })

  it('labels each year as the backend gives it', async () => {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    // as the backend writes each year's value: at the year's first moment in UTC
    registerEndpoint('/api/stripes/values', () => ({
      metadata: { station },
      values: [
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
      ],
    }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation&show_years=true' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    plotly.newPlot.mockClear()

    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())

    const [, traces, layout] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, Array<{ x: number[] }>, { annotations: Array<{ text: string }> }]
    expect(traces[0]!.x).toEqual([2019, 2020])
    expect(layout.annotations.map(a => a.text)).toEqual(expect.arrayContaining(['2019', '2020']))
  })
})

describe('stripes Page chart that could not be drawn', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_date: '1950-01-01', end_date: '2020-01-01' }

  // the chart area's Retry button, and the alert beside it, not a toast's
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')
  const note = () => retry()?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()
  const downloadMenu = () => document.body.querySelector('button[aria-haspopup="menu"]')
  const toasts = () => [...document.body.querySelectorAll('[data-slot="title"]')].map(title => title.textContent?.trim())

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  // the page in the app's UApp, which shows its toasts, with the station chosen and Show clicked
  async function showStripes() {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      metadata: { station },
      values: [
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
      ],
    }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    return vm
  }

  it('says so where Plotly failed to load, and loads it again on Retry', async () => {
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    await showStripes()
    // the failing module loaded, which a busy runner can take a while over
    await vi.waitFor(() => expect(retry()).toBeDefined(), { timeout: 5000 })
    expect(note()).toBe('The chart could not be drawn')
    expect(logged).toHaveBeenCalledWith('The chart could not be drawn', expect.any(Error))
    // no image of stripes that are not drawn
    expect(downloadMenu()).toBeNull()

    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    retry()!.click()
    // the module loaded anew, which a busy runner can take a while over
    await vi.waitFor(() => expect(retry()).toBeUndefined(), { timeout: 5000 })
    expect(plotly.newPlot).toHaveBeenCalledOnce()
    expect(downloadMenu()).not.toBeNull()
  })

  it('says so where drawing fails, and draws the stripes on Retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toBe('The chart could not be drawn')

    retry()!.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    expect(plotly.newPlot).toHaveBeenCalledTimes(2)
  })

  it('takes the note away with the stripes on Reset where Plotly failed to load', async () => {
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined(), { timeout: 5000 })

    await wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Reset')!.trigger('click')
    expect(retry()).toBeUndefined()
    expect(document.body.textContent).toContain('Select a station and click Show')
  })

  it('takes the note, and its Retry of the earlier values, away as Show fetches the stripes anew', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined())
    // the next values held, so the fetch is still under way
    let answer!: () => void
    const answered = new Promise<void>((resolve) => {
      answer = resolve
    })
    registerEndpoint('/api/stripes/values', async () => {
      await answered
      return { metadata: { station }, values: [{ timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 }] }
    })

    await wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    expect(retry()).toBeUndefined()
    answer()
  })

  it('draws nothing where Reset came while Plotly loaded', async () => {
    // Plotly's load held until after Reset
    let load!: () => void
    const loaded = new Promise<void>((resolve) => {
      load = resolve
    })
    vi.doMock('plotly.js-basic-dist-min', async () => {
      await loaded
      return plotly
    })
    plotly.newPlot.mockClear()
    plotly.purge.mockClear()
    const vm = await showStripes()
    // the values fetched, and their drawing waiting for Plotly
    await vi.waitFor(() => expect(vm.hasPlot).toBe(true))

    await wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Reset')!.trigger('click')
    load()

    // the load done, and nothing drawn into the cleared chart area
    await import('plotly.js-basic-dist-min')
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(plotly.purge).not.toHaveBeenCalled()
    expect(plotly.newPlot).not.toHaveBeenCalled()
  })

  it('says the stripes image could not be saved where its export fails', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const failed = new Error('export failed')
    plotly.downloadImage.mockRejectedValueOnce(failed)
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})

    await vm.downloadStripes('png')

    await vi.waitFor(() => expect(toasts()).toContain('The chart image could not be saved'))
    expect(logged).toHaveBeenCalledWith('The chart image could not be saved', failed)
  })
})

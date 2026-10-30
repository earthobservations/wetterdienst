import type { H3Event } from 'h3'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError, setResponseStatus } from 'h3'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { UApp } from '#components'
import { clearNuxtData, useToast } from '#imports'
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
  Icons: { camera: { width: 1000, height: 1000, path: '' } },
}))
vi.mock('plotly.js-basic-dist-min', () => plotly)

// Nuxt's reload of the page: the test's document does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

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
    const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
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
  const tempelhof = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  const potsdam = { station_id: '3987', name: 'Potsdam', region: 'Brandenburg', latitude: 52.38, longitude: 13.06, start_timestamp: '1893-01-01', end_timestamp: '2020-01-01' }

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
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

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
      series: { station },
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

  it('names the value and the trend of the hover texts in the active language', async () => {
    // they read "Value:" and "Trend:" in every language (GH-2610)
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as any).setLocale('de')
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
      values: [
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
      ],
    }))
    try {
      wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=temperature&show_timeseries=true&show_trendline=true' })
      const vm = wrapper.vm as any
      await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
      vm.selectedStation = station
      await nextTick()
      plotly.newPlot.mockClear()

      await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Anzeigen')!.trigger('click')
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())

      const [, traces] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, Array<{ hovertemplate?: string }>]
      const hovers = traces.map(trace => trace.hovertemplate).filter(Boolean)
      // the bar's too is formatted, as Plotly writes an unformatted number with a point in every language
      expect(hovers).toContain('<b>%{x}</b><br>Wert: %{customdata:.2f}<extra></extra>')
      expect(hovers).toContain('<b>%{x}</b><br>Trend: %{customdata:.2f}<extra></extra>')
      expect(hovers.join()).not.toContain('Value')
    }
    finally {
      await (harness.vm as any).setLocale('en')
      harness.unmount()
    }
  })

  // Plotly writes the numbers of its hover texts with the layout's separators, and a point where
  // there are none (GH-2971)
  it.each([
    ['en', 'Show', /^\.,$/],
    ['de', 'Anzeigen', /^,\.$/],
    // the group is a no-break space, which differs by language, so only its kind is pinned
    ['fr', 'Afficher', /^,\s$/],
    ['pl', 'Pokaż', /^,\s$/],
  ])('draws the chart with the separators of %s', async (language, show, separators) => {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as any).setLocale(language)
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
      values: [
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
      ],
    }))
    try {
      wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=temperature' })
      const vm = wrapper.vm as any
      await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
      vm.selectedStation = station
      await nextTick()
      plotly.newPlot.mockClear()

      await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === show)!.trigger('click')
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())

      const [, , layout] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, unknown, { separators: string }]
      expect(layout.separators).toMatch(separators)
    }
    finally {
      await (harness.vm as any).setLocale('en')
      harness.unmount()
    }
  })

  it('draws the chart again in the language it is switched to', async () => {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
      values: [
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
      ],
    }))
    try {
      wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=temperature' })
      const vm = wrapper.vm as any
      await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
      vm.selectedStation = station
      await nextTick()
      plotly.newPlot.mockClear()
      await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())
      expect((plotly.newPlot.mock.lastCall as unknown as [unknown, unknown, { separators: string }])[2].separators).toBe('.,')

      await (harness.vm as any).setLocale('de')
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(2))
      expect((plotly.newPlot.mock.lastCall as unknown as [unknown, unknown, { separators: string }])[2].separators).toBe(',.')
    }
    finally {
      await (harness.vm as any).setLocale('en')
      harness.unmount()
    }
  })
})

// a failing Plotly load can take seconds on a busy runner, past the default test timeout
describe('stripes Page chart that could not be drawn', { timeout: 15_000 }, () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  // the chart area's Retry button, and the alert beside it, not a toast's
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')
  const note = () => retry()?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()
  const downloadMenu = () => document.body.querySelector('button[aria-haspopup="menu"]')
  const toasts = () => [...document.body.querySelectorAll('[data-slot="title"]')].map(title => title.textContent?.trim())

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(async () => {
    // Plotly mocked back, and that mock taken up at once: vitest resolves the mocks queued for the
    // next import in parallel, so this one, still queued, could win over the next test's own
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    await import('plotly.js-basic-dist-min')
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
      series: { station },
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
    expect(note()).toBe('The chart could not be drawn. Its code could not be loaded. If trying again does not help, reload the page.')
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
    const vm = await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined())
    // the next values held, so the fetch is still under way
    let answer!: () => void
    const answered = new Promise<void>((resolve) => {
      answer = resolve
    })
    registerEndpoint('/api/stripes/values', async () => {
      await answered
      return { series: { station }, values: [{ timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 }] }
    })

    await wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    expect(retry()).toBeUndefined()
    // the held fetch let finish here, so it draws nothing into the next test
    answer()
    await vi.waitFor(() => expect(vm.isLoading).toBe(false))
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

  it('draws the stripes again from the values it has where a display option changes, and fetches nothing', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    // a request is sent as the fetch starts, so one sent for the option is seen by the redraw
    const fetched = vi.spyOn(globalThis, '$fetch')
    plotly.newPlot.mockClear()

    vm.showYears = false
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())
    const [, , layout] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, unknown, { annotations: Array<{ text: string }> }]
    expect(layout.annotations.map(a => a.text)).not.toContain('2020')
    expect(fetched).not.toHaveBeenCalled()
    expect(vm.isLoading).toBe(false)
  })

  it('saves the stripes drawn again off screen, the light chart whatever the page shows, and leaves the chart as it is', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const [shown, , shownLayout] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, unknown, { annotations: Array<{ text: string }> }]
    plotly.newPlot.mockClear()
    plotly.purge.mockClear()
    plotly.downloadImage.mockClear()

    await vm.downloadStripes('png')

    const [copy, traces, layout] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, unknown[], { annotations: Array<{ text: string }> }]
    expect(copy).not.toBe(shown)
    expect(copy.getAttribute('aria-hidden')).toBe('true')
    // the same stripes, with the same labels
    expect(traces.length).toBeGreaterThan(0)
    expect(layout.annotations.map(a => a.text)).toEqual(shownLayout.annotations.map(a => a.text))
    expect(plotly.downloadImage).toHaveBeenCalledWith(copy, expect.objectContaining({ format: 'png' }))
    // the copy is gone once saved, and the chart shown was not touched
    expect(plotly.purge).toHaveBeenCalledWith(copy)
    expect(copy.isConnected).toBe(false)
    expect(plotly.purge).not.toHaveBeenCalledWith(shown)
  })

  // zoomed in: Plotly holds the ranges it shows, which the layout built from the data does not know
  const zoomed = { _fullLayout: { xaxis: { range: [2019.5, 2019.9] }, yaxis: { range: [0.2, 0.8] } } }
  const rangesOf = (layout: unknown) => layout as { xaxis: { range: number[], autorange?: boolean }, yaxis: { range: number[] } }

  it('saves the stripes at the zoom they are shown in', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    Object.assign((plotly.newPlot.mock.lastCall as unknown as [HTMLElement])[0], zoomed)
    plotly.newPlot.mockClear()

    await vm.downloadStripes('png')

    const [copy, , layout] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, unknown, unknown]
    expect(copy.getAttribute('aria-hidden')).toBe('true')
    expect(rangesOf(layout).xaxis).toMatchObject({ range: [2019.5, 2019.9], autorange: false })
    expect(rangesOf(layout).yaxis.range).toEqual([0.2, 0.8])
  })

  it('draws the stripes again at the zoom they are shown in where the colour scheme switches, which a reset still goes back from', async () => {
    await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const [shown] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement]
    Object.assign(shown, zoomed)
    plotly.newPlot.mockClear()
    plotly.relayout.mockClear()
    document.documentElement.classList.add('dark')
    try {
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())
      // plotted in the range of its own (Plotly takes that for the one a reset goes back to), then moved
      expect(rangesOf((plotly.newPlot.mock.lastCall as unknown as unknown[])[2]).xaxis.range).not.toEqual([2019.5, 2019.9])
      await vi.waitFor(() => expect(plotly.relayout).toHaveBeenCalledWith(shown, expect.objectContaining({ 'xaxis.range': [2019.5, 2019.9], 'yaxis.range': [0.2, 0.8] })))
      expect(shown.dataset.chartScheme).toBe('dark')
    }
    finally {
      document.documentElement.classList.remove('dark')
    }
  })

  it('says the scheme the chart is drawn in whatever the relayout after the plot does', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const [shown] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement]
    expect(shown.dataset.chartScheme).toBe('light')
    Object.assign(shown, zoomed)
    plotly.newPlot.mockClear()
    plotly.relayout.mockClear()
    // the move to the zoom fails after the chart was plotted in the colours of the dark scheme
    plotly.relayout.mockRejectedValueOnce(new Error('relayout failed'))
    document.documentElement.classList.add('dark')
    try {
      await vi.waitFor(() => expect(plotly.relayout).toHaveBeenCalledOnce())
      await vi.waitFor(() => expect(shown.dataset.chartScheme).toBe('dark'))
    }
    finally {
      document.documentElement.classList.remove('dark')
    }
  })

  it('moves nothing of a drawing that a newer one has replaced', async () => {
    await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const [shown] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement]
    Object.assign(shown, zoomed)
    plotly.newPlot.mockClear()
    plotly.relayout.mockClear()
    // the drawing for the dark scheme held in Plotly, and the scheme switched back, which draws the chart again
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    plotly.newPlot.mockImplementationOnce(async () => {
      await held
    })
    document.documentElement.classList.add('dark')
    try {
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())
      document.documentElement.classList.remove('dark')
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(2))
      await vi.waitFor(() => expect(plotly.relayout).toHaveBeenCalledOnce())
      release()
      await new Promise(resolve => setTimeout(resolve, 50))
      // the newer drawing's move, and none of the older one's
      expect(plotly.relayout).toHaveBeenCalledOnce()
    }
    finally {
      document.documentElement.classList.remove('dark')
    }
  })

  it('has the camera of the modebar save the same, in the place of Plotly\'s own', async () => {
    await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const [, , , config] = plotly.newPlot.mock.lastCall as unknown as [HTMLElement, unknown, unknown, { modeBarButtonsToRemove: string[], modeBarButtonsToAdd: { name: string, title: string, click: () => void }[], toImageButtonOptions?: unknown }]
    expect(config.modeBarButtonsToRemove).toContain('toImage')
    const [camera] = config.modeBarButtonsToAdd
    expect([camera!.name, camera!.title]).toEqual(['toImage', 'Download plot as a PNG'])
    plotly.downloadImage.mockClear()
    camera!.click()
    await vi.waitFor(() => expect(plotly.downloadImage).toHaveBeenCalledOnce())
    // the size Plotly's own camera had saved, 1400 px wide at twice the size
    expect(plotly.downloadImage).toHaveBeenCalledWith(expect.any(HTMLElement), expect.objectContaining({ format: 'png', width: 1400, scale: 2 }))
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

describe('stripes Page values that could not be fetched', () => {
  const tempelhof = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  const potsdam = { station_id: '3987', name: 'Potsdam', region: 'Brandenburg', latitude: 52.38, longitude: 13.06, start_timestamp: '1893-01-01', end_timestamp: '2020-01-01' }
  const values = (station: typeof tempelhof) => ({
    series: { station },
    values: [
      { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
      { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
    ],
  })

  // the chart area's note of the failed fetch
  const note = () => [...document.body.querySelectorAll('[role="alert"] > span')].map(line => line.textContent?.trim()).join(' / ') || undefined
  const downloadMenu = () => document.body.querySelector('button[aria-haspopup="menu"]')

  // an answer held until the test lets it go
  function held<T>(answer: () => T) {
    let release!: () => void
    const released = new Promise<void>((resolve) => {
      release = resolve
    })
    const handler = async () => {
      await released
      return answer()
    }
    return { release, handler }
  }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the requests the page makes, each settled however it ended
  let requests: Promise<unknown>[] = []
  function recordRequests() {
    const original = globalThis.$fetch
    requests = []
    vi.spyOn(globalThis, '$fetch').mockImplementation(((...args: Parameters<typeof original>) => {
      const request = original(...args)
      requests.push(request.catch(() => {}))
      return request
    }) as typeof original)
  }
  // every request recorded settled, and the page done with its answer
  async function settled() {
    await Promise.all(requests)
    await new Promise(resolve => setTimeout(resolve, 0))
  }

  const button = (label: string) => wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === label)!

  // the page in the app's UApp, with the stations fetched
  async function mountPage() {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [tempelhof, potsdam] }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(2))
    return vm
  }

  async function show(vm: any, station: typeof tempelhof) {
    vm.selectedStation = station
    await nextTick()
    await button('Show').trigger('click')
  }

  it('tells the backend\'s reason in the chart area', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', (event) => {
      setResponseStatus(event, 404)
      return { detail: 'No precipitation data for station 1048' }
    })
    const vm = await mountPage()
    await show(vm, tempelhof)

    await vi.waitFor(() => expect(note()).toBe('Failed to load data / No precipitation data for station 1048'))
    expect(vm.isLoading).toBe(false)
    expect(document.body.textContent).not.toContain('Select a station and click Show')

    // Reset takes the note away
    await button('Reset').trigger('click')
    expect(note()).toBeUndefined()
    expect(document.body.textContent).toContain('Select a station and click Show')
  })

  it('takes another station\'s stripes away as this one\'s are fetched, and tells why they could not be', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', () => values(tempelhof))
    const vm = await mountPage()
    await show(vm, tempelhof)
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())

    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    plotly.purge.mockClear()
    await show(vm, potsdam)
    // Tempelhof's stripes gone while Potsdam's are fetched
    expect(vm.hasPlot).toBe(false)
    expect(plotly.purge).toHaveBeenCalled()
    expect(downloadMenu()).toBeNull()

    failing.release()
    await vi.waitFor(() => expect(note()).toBe('Failed to load data / 502 Bad Gateway'))
    expect(vm.hasPlot).toBe(false)
    expect(vm.lastFetchedData).toBeNull()
  })

  it('offers no image of stripes that could not be drawn, while or after they are fetched anew in vain', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', () => values(tempelhof))
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    const vm = await mountPage()
    await show(vm, tempelhof)
    await vi.waitFor(() => expect(vm.plotFailed).toBe(true))

    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    await button('Show').trigger('click')
    // no empty chart area, with an image of nothing offered
    expect(vm.hasPlot).toBe(false)
    expect(downloadMenu()).toBeNull()

    failing.release()
    await vi.waitFor(() => expect(note()).toBe('Failed to load data / 502 Bad Gateway'))
    expect(vm.hasPlot).toBe(false)
    expect(downloadMenu()).toBeNull()
  })

  it('keeps the station\'s stripes, and tells the failure above them, where Show fetches them anew in vain', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', () => values(tempelhof))
    const vm = await mountPage()
    await show(vm, tempelhof)
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())

    registerEndpoint('/api/stripes/values', () => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    vm.startYear = 2019
    await nextTick()
    await button('Show').trigger('click')

    await vi.waitFor(() => expect(note()).toBe('Failed to load data / 502 Bad Gateway'))
    expect(vm.hasPlot).toBe(true)
    expect(vm.lastFetchedData).not.toBeNull()
    expect(downloadMenu()).not.toBeNull()
  })

  it('stops a fetch on Reset, where no stripes were shown, and draws nothing', async () => {
    const vm = await mountPage()
    recordRequests()
    const answer = held(() => values(tempelhof))
    registerEndpoint('/api/stripes/values', answer.handler)
    plotly.newPlot.mockClear()
    await show(vm, tempelhof)
    expect(vm.isLoading).toBe(true)
    expect(button('Reset').attributes('disabled')).toBeUndefined()
    await button('Reset').trigger('click')
    expect(vm.isLoading).toBe(false)

    answer.release()
    await settled()
    expect(plotly.newPlot).not.toHaveBeenCalled()
    expect(vm.hasPlot).toBe(false)
    expect(document.body.textContent).toContain('Select a station and click Show')
  })

  it('tells nothing where the kind changed while a fetch that then failed was under way', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    const vm = await mountPage()
    recordRequests()
    await show(vm, tempelhof)
    expect(vm.isLoading).toBe(true)

    vm.kind = 'temperature'
    await nextTick()
    expect(vm.isLoading).toBe(false)

    failing.release()
    await settled()
    expect(note()).toBeUndefined()
    expect(vm.fetchError).toBeNull()
  })

  it('draws nothing where another station was chosen while the fetch was under way', async () => {
    const vm = await mountPage()
    recordRequests()
    const answer = held(() => values(tempelhof))
    registerEndpoint('/api/stripes/values', answer.handler)
    plotly.newPlot.mockClear()
    await show(vm, tempelhof)
    expect(vm.isLoading).toBe(true)

    vm.selectedStation = potsdam
    await nextTick()
    // the fetch stopped at once: Potsdam's stripes can be asked for
    expect(vm.isLoading).toBe(false)
    expect(button('Show').attributes('disabled')).toBeUndefined()
    answer.release()
    await settled()
    expect(plotly.newPlot).not.toHaveBeenCalled()
    expect(vm.hasPlot).toBe(false)
    expect(vm.lastFetchedData).toBeNull()
    expect(vm.isLoading).toBe(false)
  })

  it('tells nothing where another station was chosen while a fetch that then failed was under way', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    const vm = await mountPage()
    recordRequests()
    await show(vm, tempelhof)

    vm.selectedStation = potsdam
    await nextTick()
    // the fetch stopped at once: Potsdam's stripes can be asked for
    expect(vm.isLoading).toBe(false)
    expect(button('Show').attributes('disabled')).toBeUndefined()
    failing.release()
    await settled()
    expect(note()).toBeUndefined()
    expect(vm.fetchError).toBeNull()
    expect(vm.isLoading).toBe(false)
  })
})

describe('stripes Page chart whose Plotly chunk a redeploy replaced', { timeout: 15_000 }, () => {
  // A redeploy replaces Plotly's hashed chunk under an open tab: every Retry asks for the gone chunk
  // again and fails, and only reloading the page loads the new one
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  const button = (label: string) => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === label)
  const note = () => button('Retry')?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()
  const hint = 'If trying again does not help, reload the page.'

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(async () => {
    // Plotly mocked back, and that mock taken up at once, as the tests above do
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    await import('plotly.js-basic-dist-min')
    vi.restoreAllMocks()
    reloadNuxtApp.mockClear()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the page with the station chosen and Show clicked, while Plotly's chunk fails to load
  async function shownWithoutPlotly() {
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
      values: [
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
      ],
    }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    button('Show')!.click()
    // the failing module loaded, which a busy runner can take a while over
    await vi.waitFor(() => expect(button('Retry')).toBeDefined(), { timeout: 5000 })
  }

  it('says to reload the page, and reloads it, where Plotly failed to load', async () => {
    await shownWithoutPlotly()
    // the two apart, as a screen reader reads the alert
    expect(note()).toBe(`The chart could not be drawn. Its code could not be loaded. ${hint}`)
    button('Reload page')!.click()
    // forced: unforced, Nuxt drops a second click within ten seconds of a first that did not help
    expect(reloadNuxtApp).toHaveBeenCalledExactlyOnceWith({ force: true })
  })

  it('offers no reload once Plotly loaded and only its drawing failed', async () => {
    // a reload loads nothing the drawing needs: Retry is the way
    await shownWithoutPlotly()
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    plotly.newPlot.mockClear()
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    button('Retry')!.click()
    // the module loaded anew, which a busy runner can take a while over
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    await vi.waitFor(() => expect(note()).toBe('The chart could not be drawn'))
    expect(button('Reload page')).toBeUndefined()
  })
})

describe('stripes Page requests answered with a 500', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  // disposers of the endpoints these tests register, so none answers a later test
  const endpoints: Array<() => void> = []
  afterEach(() => {
    endpoints.splice(0).forEach(dispose => dispose())
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  // counted at the endpoint, which a request reaches however it is made
  function failing() {
    const asked = { count: 0 }
    return {
      asked,
      handler: (event: H3Event) => {
        asked.count++
        setResponseStatus(event, 500)
        return { detail: 'Upstream failed' }
      },
    }
  }

  it('asks /api/stripes/stations once', async () => {
    const { asked, handler } = failing()
    endpoints.push(registerEndpoint('/api/stripes/stations', handler))
    // precipitation, as the pages the first tests leave mounted hold the temperature stations' fetch
    wrapper = await mountSuspended(StripesPage, { route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked.count).toBeGreaterThan(0)
      expect(vm.stationsPending).toBe(false)
    })
    expect(asked.count).toBe(1)
  })

  it('asks /api/stripes/values once, and tells its error', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    endpoints.push(registerEndpoint('/api/stripes/stations', () => ({ stations: [station] })))
    const { asked, handler } = failing()
    endpoints.push(registerEndpoint('/api/stripes/values', handler))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(document.body.textContent).toContain('Upstream failed'))
    expect(asked.count).toBe(1)
  })
})

describe('stripes Page requests answered with a 503 once', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  // disposers of the endpoints these tests register, so none answers a later test
  const endpoints: Array<() => void> = []
  afterEach(() => {
    endpoints.splice(0).forEach(dispose => dispose())
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  // a 503 the first time only, as a proxy gives while the backend restarts
  function flaky(answer: unknown) {
    const asked = { count: 0 }
    return {
      asked,
      handler: (event: H3Event) => {
        asked.count++
        if (asked.count === 1) {
          setResponseStatus(event, 503)
          return { detail: 'Service Unavailable' }
        }
        return answer
      },
    }
  }

  it('asks /api/stripes/stations once more, and lists what that answer brings', async () => {
    const { asked, handler } = flaky({ stations: [station] })
    endpoints.push(registerEndpoint('/api/stripes/stations', handler))
    // precipitation, as the pages the first tests leave mounted hold the temperature stations' fetch
    wrapper = await mountSuspended(StripesPage, { route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    expect(asked.count).toBe(2)
  })

  it('asks /api/stripes/values once more, and plots what that answer brings', async () => {
    endpoints.push(registerEndpoint('/api/stripes/stations', () => ({ stations: [station] })))
    const { asked, handler } = flaky({ series: { station }, years: [{ year: 2000, value: 9.5 }] })
    endpoints.push(registerEndpoint('/api/stripes/values', handler))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(vm.hasPlot).toBe(true))
    expect(asked.count).toBe(2)
    expect(document.body.textContent).not.toContain('Service Unavailable')
  })
})

describe('stripes Page chart after a Retry', { timeout: 15_000 }, () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  // the focus Retry held fell to the page's body once a Retry that worked took the note away
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  // the stripes shown, their drawing failed, and Retry focused and pressed, its drawing held on a
  // gate that lets it draw or fail again
  async function retried() {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
      values: [{ timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 }],
    }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(retry()).toBeDefined())
    let settle!: (failure?: Error) => void
    plotly.newPlot.mockImplementationOnce(() => new Promise<void>((resolve, reject) => {
      settle = failure => failure ? reject(failure) : resolve()
    }))
    const button = retry()!
    button.focus()
    button.click()
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(2))
    // the mock takes no arguments in its type, so its call is read as Plotly's (element)
    const [chart] = plotly.newPlot.mock.calls[1] as unknown as [HTMLElement]
    return { vm, button, chart, settle }
  }

  it('hands the focus on to the stripes once they are drawn', async () => {
    const { chart, settle } = await retried()

    settle()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    await vi.waitFor(() => expect(document.activeElement).toBe(chart))
    // a browser focuses a div only with a tabindex, which the test's document does not ask for
    expect(chart.getAttribute('tabindex')).toBe('-1')
  })

  it('leaves the focus where it was moved to meanwhile', async () => {
    const { vm, settle } = await retried()
    const elsewhere = document.body.appendChild(document.createElement('button'))
    elsewhere.focus()

    settle()
    await vi.waitFor(() => expect(vm.plotFailed).toBe(false))
    await nextTick()
    expect(retry()).toBeUndefined()
    expect(document.activeElement).toBe(elsewhere)
  })

  it('keeps the focus on Retry where the stripes fail again', async () => {
    const { vm, button, settle } = await retried()

    settle(new Error('drawing failed again'))
    await vi.waitFor(() => expect(vm.plotFailures).toBe(2))
    await nextTick()
    expect(retry()).toBe(button)
    expect(document.activeElement).toBe(button)
  })
})

describe('stripes Page chart name', { timeout: 15_000 }, () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  it('names the stripes by their kind and station, as a figure', async () => {
    plotly.newPlot.mockClear()
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
      values: [{ timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 }],
    }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())

    // the mock takes no arguments in its type, so its call is read as Plotly's (element)
    const [chart] = plotly.newPlot.mock.calls[0] as unknown as [HTMLElement]
    expect(chart.getAttribute('role')).toBe('figure')
    expect(chart.getAttribute('aria-label')).toBe('Climate stripes (Precipitation) for Berlin-Tempelhof, Germany (1048)')
  })
})

describe('stripes Page station span', () => {
  // as the backend sends a station's span since GH-2439
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01T00:00:00.000000+00:00', end_timestamp: '2020-12-31T00:00:00.000000+00:00' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  let removeEndpoint: (() => void) | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    // so that its station answers no later test
    removeEndpoint?.()
    removeEndpoint = undefined
  })

  it('shows the years a chosen station has records for', async () => {
    removeEndpoint = registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    // the station as the page fetched it
    vm.selectedStation = vm.stations[0]
    await nextTick()

    expect(wrapper.text().replace(/\s+/g, ' ')).toContain('Available: 1950 - 2020')
  })
})

describe('stripes Page text alternative', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the stripes drawn for a station, as the backend answers them: a year without a value among them
  async function showStripes(route = '/stripes?kind=temperature') {
    // the station lists the earlier tests fetched are kept by their request, which this one is too
    clearNuxtData()
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      metadata: {},
      series: { station, resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', unit: 'degree_celsius' },
      values: [
        { timestamp: '2018-01-01T00:00:00+00:00', value: 8 },
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.25 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: null },
        { timestamp: '2021-01-01T00:00:00+00:00', value: 10 },
      ],
    }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    plotly.newPlot.mockClear()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())
    await vi.waitFor(() => expect(document.body.querySelector('[role="figure"]')?.getAttribute('aria-describedby')).toBeTruthy())
  }

  const figure = () => document.body.querySelector('[role="figure"]')!
  const toggle = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Show as table')

  it('describes the figure by what the stripes show, in words a screen reader reads', async () => {
    await showStripes()
    const description = document.getElementById(figure().getAttribute('aria-describedby')!)
    expect(description?.textContent?.trim()).toBe(
      'From 2018 to 2021. Lowest value 8.00 °C in 2018, highest value 10.00 °C in 2021. The values are in the table below the chart.',
    )
  })

  it('offers every year as a table behind a button that says whether it is open, and shows none before', async () => {
    await showStripes()
    expect(document.body.querySelector('table')).toBeNull()
    expect(toggle()?.getAttribute('aria-expanded')).toBe('false')

    toggle()!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    expect(toggle()?.getAttribute('aria-expanded')).toBe('true')
    // a reader finds the controlled part by id
    expect(document.getElementById(toggle()!.getAttribute('aria-controls')!)).not.toBeNull()

    const table = document.body.querySelector('table')!
    expect([...table.querySelectorAll('thead th')].map(th => [th.textContent?.trim(), th.getAttribute('scope')])).toEqual([
      ['Year', 'col'],
      ['Value (°C)', 'col'],
      ['Class', 'col'],
    ])
    // the year with no value is not drawn, so it is not listed; each year is the header of its row
    const rows = [...table.querySelectorAll('tbody tr')].map(row => [...row.children].map(cell => `${cell.tagName.toLowerCase()}:${cell.textContent?.trim()}`))
    expect(rows).toEqual([
      ['th:2018', 'td:8.00', 'td:Much cooler'],
      ['th:2019', 'td:9.25', 'td:Warmer'],
      ['th:2021', 'td:10.00', 'td:Much warmer'],
    ])
    expect(table.querySelector('caption')?.textContent?.trim()).toBe(figure().getAttribute('aria-label'))
  })

  it('puts the scrolling table in a region the keyboard reaches, and says what a class is', async () => {
    await showStripes()
    toggle()!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    const region = document.body.querySelector('[role="region"]')!
    expect(region.getAttribute('tabindex')).toBe('0')
    expect(region.getAttribute('aria-label')).toBe(figure().getAttribute('aria-label'))
    expect(region.contains(document.body.querySelector('table'))).toBe(true)
    expect(document.body.textContent).toContain('Class: where the year lies between the coolest and the warmest year shown')
  })

  it('names the classes of a precipitation series by wet and dry', async () => {
    await showStripes('/stripes?kind=precipitation')
    toggle()!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    expect([...document.body.querySelectorAll('tbody tr')].map(row => row.lastElementChild?.textContent?.trim())).toEqual(['Much drier', 'Wetter', 'Much wetter'])
  })

  it('has no table and no description once the stripes are cleared', async () => {
    await showStripes()
    wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Reset')!.trigger('click')
    await vi.waitFor(() => expect(toggle()).toBeUndefined())
    expect(figure().getAttribute('aria-describedby')).toBeNull()
  })
})

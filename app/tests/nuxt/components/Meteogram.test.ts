import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Meteogram from '~/components/Meteogram.vue'

// Plotly draws nothing in the test's document: its calls are recorded
const plotly = vi.hoisted(() => ({
  newPlot: vi.fn(async () => {}),
  relayout: vi.fn(async () => {}),
  purge: vi.fn(),
}))
vi.mock('plotly.js-basic-dist-min', () => plotly)

// Nuxt's reload of the page: the test's document does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

// a day of hourly temperatures, which the meteogram draws as its temperature panel
const values = Array.from({ length: 24 }, (_, hour) => ({
  station_id: '10384',
  resolution: 'hourly',
  dataset: 'small',
  parameter: 'temperature_air_mean_2m',
  timestamp: `2026-10-01T${String(hour).padStart(2, '0')}:00:00+00:00`,
  value: 10 + hour / 4,
  quality: null,
}))

// a failing Plotly load can take seconds on a busy runner, past the default test timeout
describe('meteogram chart that could not be drawn', { timeout: 15_000 }, () => {
  // the chart area's Retry button, and the alert beside it
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')
  const note = () => retry()?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  // mounted, then handed its values, as the meteogram page hands them once they are fetched
  async function showMeteogram() {
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values })
  }

  afterEach(async () => {
    // Plotly mocked back, and that mock taken up at once: vitest resolves the mocks queued for the
    // next import in parallel, so this one, still queued, could win over the next test's own
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    await import('plotly.js-basic-dist-min')
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  it('says so where Plotly failed to load, and loads it again on Retry', async () => {
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    await showMeteogram()
    // the failing module loaded, which a busy runner can take a while over
    await vi.waitFor(() => expect(retry()).toBeDefined(), { timeout: 5000 })
    expect(note()).toBe('The chart could not be drawn. Its code could not be loaded. If trying again does not help, reload the page.')
    expect(logged).toHaveBeenCalledWith('The chart could not be drawn', expect.any(Error))

    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    retry()!.click()
    // the module loaded anew, which a busy runner can take a while over
    await vi.waitFor(() => expect(retry()).toBeUndefined(), { timeout: 5000 })
    expect(plotly.newPlot).toHaveBeenCalledOnce()
  })

  it('says so where drawing fails, and draws the chart on Retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    await showMeteogram()
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toBe('The chart could not be drawn')

    retry()!.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    expect(plotly.newPlot).toHaveBeenCalledTimes(2)
  })

  it('says nothing where a drawing fails that newer values have replaced, and the newer one draws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    // the first drawing held, to fail once newer values have come in
    let fail!: (error: Error) => void
    plotly.newPlot.mockImplementationOnce(() => new Promise((_, reject) => {
      fail = reject
    }))
    await showMeteogram()
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())
    await wrapper!.setProps({ values: values.slice(1) })
    fail(new Error('drawing failed'))

    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(2))
    await vi.waitFor(() => expect((wrapper!.vm as any).renderFailed).toBe(false))
    // never told: the alert was not mounted for it
    expect((wrapper!.vm as any).renderFailures).toBe(0)
    expect(retry()).toBeUndefined()
  })
})

describe('meteogram chart whose code a redeploy replaced', { timeout: 15_000 }, () => {
  // A redeploy replaces the chart code's hashed chunks under an open tab: every Retry asks for the
  // gone chunk again and fails, and only reloading the page loads the new one
  const button = (label: string) => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === label)
  const note = () => button('Retry')?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()
  const hint = 'If trying again does not help, reload the page.'

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(async () => {
    // the modules mocked back, and those mocks taken up at once, as the tests above do
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    await import('plotly.js-basic-dist-min')
    vi.doUnmock('suncalc')
    await import('suncalc')
    vi.restoreAllMocks()
    reloadNuxtApp.mockClear()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // mounted, then handed its values, with a station's position, which the day bands need suncalc for
  async function showMeteogram() {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    wrapper = await mountSuspended(Meteogram, {
      props: { values: [], stationName: 'Berlin', stationCoords: { latitude: 52.47, longitude: 13.4 } },
      attachTo: document.body,
    })
    await wrapper.setProps({ values })
    // the failing module loaded, which a busy runner can take a while over
    await vi.waitFor(() => expect(button('Retry')).toBeDefined(), { timeout: 5000 })
  }

  it.each([
    ['Plotly', 'plotly.js-basic-dist-min'],
    ['suncalc', 'suncalc'],
  ])('says to reload the page, and reloads it, where %s failed to load', async (_, module) => {
    vi.doMock(module, () => {
      throw new Error('chunk failed to load')
    })
    await showMeteogram()
    // the two apart, as a screen reader reads the alert
    expect(note()).toBe(`The chart could not be drawn. Its code could not be loaded. ${hint}`)
    button('Reload page')!.click()
    // forced: unforced, Nuxt drops a second click within ten seconds of a first that did not help
    expect(reloadNuxtApp).toHaveBeenCalledExactlyOnceWith({ force: true })
  })

  it('offers no reload once the code loaded and only the drawing failed', async () => {
    // a reload loads nothing the drawing needs: Retry is the way
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    await showMeteogram()
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

describe('meteogram low clouds', { timeout: 15_000 }, () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  it('draws DWD\'s low cloud cover under its canonical name, cloud_cover_below_2km', async () => {
    // the cloud panel is drawn for a total cover, as MOSMIX and DMO carry beside the low one
    const clouds = ['cloud_cover_total', 'cloud_cover_below_2km'].flatMap(parameter =>
      values.map(value => ({ ...value, parameter, value: 40 })))
    plotly.newPlot.mockClear()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: [...values, ...clouds] })

    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    // the mock takes no arguments in its type, so its call is read as Plotly's (element, traces)
    const [, traces] = plotly.newPlot.mock.calls[0] as unknown as [unknown, { name: string }[]]
    expect(traces.map(trace => trace.name)).toContain('Low Clouds %')
  })
})

describe('meteogram chart after a Retry', { timeout: 15_000 }, () => {
  // the focus Retry held fell to the page's body once a Retry that worked took the note away
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the chart's drawing failed, and Retry focused and pressed, its drawing held on a gate that
  // lets it draw or fail again
  async function retried() {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values })
    await vi.waitFor(() => expect(retry()).toBeDefined(), { timeout: 5000 })
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
    return { button, chart, settle }
  }

  it('hands the focus on to the chart once it is drawn', async () => {
    const { chart, settle } = await retried()

    settle()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    await vi.waitFor(() => expect(document.activeElement).toBe(chart))
    // a browser focuses a div only with a tabindex, which the test's document does not ask for
    expect(chart.getAttribute('tabindex')).toBe('-1')
  })

  it('leaves the focus where it was moved to meanwhile', async () => {
    const { settle } = await retried()
    const elsewhere = document.body.appendChild(document.createElement('button'))
    elsewhere.focus()

    settle()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    await vi.waitFor(() => expect((wrapper!.vm as any).renderFailed).toBe(false))
    await wrapper!.vm.$nextTick()
    expect(document.activeElement).toBe(elsewhere)
  })

  it('keeps the focus on Retry where the chart fails again', async () => {
    const { button, settle } = await retried()

    settle(new Error('drawing failed again'))
    await vi.waitFor(() => expect((wrapper!.vm as any).renderFailures).toBe(2))
    await wrapper!.vm.$nextTick()
    expect(retry()).toBe(button)
    expect(document.activeElement).toBe(button)
  })
})

describe('meteogram chart name', { timeout: 15_000 }, () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the chart Plotly drew into, by the role and the name a screen reader announces it with
  async function drawnInto(stationName: string | null) {
    plotly.newPlot.mockClear()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName }, attachTo: document.body })
    await wrapper.setProps({ values })
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    // the mock takes no arguments in its type, so its call is read as Plotly's (element)
    const [chart] = plotly.newPlot.mock.calls[0] as unknown as [HTMLElement]
    return [chart.getAttribute('role'), chart.getAttribute('aria-label')]
  }

  it('names the chart by its station, as a figure', async () => {
    expect(await drawnInto('Berlin')).toEqual(['figure', 'Forecast chart for Berlin'])
  })

  it('names the chart without a station where it is given none', async () => {
    expect(await drawnInto(null)).toEqual(['figure', 'Forecast chart'])
  })
})

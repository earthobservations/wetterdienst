import process from 'node:process'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
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
  parameter: 'temperature_air_2m',
  timestamp: `2026-10-01T${String(hour).padStart(2, '0')}:00:00+00:00`,
  value: 10 + hour / 4,
  quality_flags: null,
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

describe('meteogram temperature band', { timeout: 15_000 }, () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // dwd/mosmix station 10147, the run of 2026-10-15 04:00 UTC, as /api/values answered: the hourly
  // temperature from 04:00 to 06:00 the next day, and `tx` and `tn` stamped at 06:00 and 18:00, each
  // the extreme of the 12 hours before it (GH-2647)
  const temperature = [8.2, 8.3, 8.7, 9.7, 10.9, 12.5, 13.8, 15.1, 16.0, 16.5, 16.7, 16.5, 15.7, 14.6, 13.8, 13.3, 12.7, 12.6, 12.5, 12.6, 12.6, 12.5, 12.6, 12.6, 12.6, 12.8, 13.1]
  const stamped = {
    temperature_air_max_2m_last_12h: [['2026-10-15T06:00:00+00:00', 10.3], ['2026-10-15T18:00:00+00:00', 17.4], ['2026-10-16T06:00:00+00:00', 13.9]],
    temperature_air_min_2m_last_12h: [['2026-10-15T06:00:00+00:00', 6.5], ['2026-10-15T18:00:00+00:00', 8.0], ['2026-10-16T06:00:00+00:00', 11.6]],
  } as const
  const rows = [
    ...temperature.map((value, i) => ({ ...values[0]!, parameter: 'temperature_air_2m', timestamp: new Date(Date.parse('2026-10-15T04:00:00Z') + i * 3_600_000).toISOString(), value })),
    ...Object.entries(stamped).flatMap(([parameter, points]) => points.map(([timestamp, value]) => ({ ...values[0]!, parameter, timestamp, value }))),
  ]

  it('holds each maximum and minimum across the hours it covers, so the temperature stays inside', async () => {
    plotly.newPlot.mockClear()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Hamburg' }, attachTo: document.body })
    await wrapper.setProps({ values: rows })
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    const [, traces] = plotly.newPlot.mock.calls[0] as unknown as [unknown, { name: string, x: string[], y: number[] }[]]
    const trace = (name: string) => traces.find(t => t.name === name)!
    const [mean, high, low] = [trace('Mean Temp °C'), trace('Max Temp °C'), trace('Min Temp °C')]
    // an hour belongs to the window that ends at or after it, which a date's one point holds
    const boundAt = (bound: typeof high, hour: string) => bound.y[bound.x.indexOf(hour)]!
    expect(mean.x).toHaveLength(temperature.length)
    for (const [i, hour] of mean.x.entries()) {
      expect(mean.y[i]!, `${hour} above its maximum`).toBeLessThanOrEqual(boundAt(high, hour))
      expect(mean.y[i]!, `${hour} below its minimum`).toBeGreaterThanOrEqual(boundAt(low, hour))
    }
    // as drawn between the stamps, 16.7 degrees at 14:00 was above the maximum line (14.1)
    expect(boundAt(high, '2026-10-15T14:00:00.000Z')).toBe(17.4)
    expect(boundAt(low, '2026-10-15T14:00:00.000Z')).toBe(8)
  })

  it('draws no band, and calls the curve the temperature, where the maximum and minimum hold no value', async () => {
    plotly.newPlot.mockClear()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Hamburg' }, attachTo: document.body })
    await wrapper.setProps({ values: [...rows.filter(row => row.parameter === 'temperature_air_2m'), ...Object.entries(stamped).flatMap(([parameter, points]) => points.map(([timestamp]) => ({ ...values[0]!, parameter, timestamp, value: null })))] })
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    const [, traces] = plotly.newPlot.mock.calls[0] as unknown as [unknown, { name: string }[]]
    expect(traces.map(trace => trace.name)).not.toContain('Max Temp °C')
    expect(traces.map(trace => trace.name)).not.toContain('Mean Temp °C')
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

describe('meteogram numbers and day labels in the active language', { timeout: 15_000 }, () => {
  // a day of hourly temperatures and rain, the 15th of October: a day of the month no month number
  // can be taken for, so the order of the two shows
  const day = Array.from({ length: 24 }, (_, hour) => ({
    station_id: '10384',
    resolution: 'hourly',
    dataset: 'small',
    parameter: 'temperature_air_2m',
    timestamp: `2026-10-15T${String(hour).padStart(2, '0')}:00:00+00:00`,
    value: 10 + hour / 4,
    quality_flags: null,
  }))
  const rain = day.map(value => ({ ...value, parameter: 'precipitation_amount_last_1h', value: 0.25 }))

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  let harness: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(async () => {
    wrapper?.unmount()
    wrapper = undefined
    // the URL back to none, which the next test's chart would read its compact view from
    await useRouter().replace({ query: {} })
    await (harness?.vm as any)?.setLocale('en')
    harness?.unmount()
    harness = undefined
    document.body.innerHTML = ''
  })

  async function inLanguage(language: string) {
    harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as any).setLocale(language)
  }

  async function showMeteogram() {
    plotly.newPlot.mockClear()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: [...day, ...rain] })
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
  }

  // The compact view, which the Meteogram also writes to the URL (`?compact=true`) with a navigation of
  // the router. That navigation runs on after the test, and a test that ends before it has finished
  // leaves it to the teardown of the test's document, where its `history` is gone (GH-3064): wait for
  // the URL.
  async function showCompact() {
    ;(wrapper!.vm as any).compact = true
    await wrapper!.vm.$nextTick()
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.compact).toBe('true'))
  }

  // the mock takes no arguments in its type, so its call is read as Plotly's (element, traces, layout)
  const layoutDrawn = () => (plotly.newPlot.mock.lastCall as unknown as [unknown, unknown, { separators: string }])[2]

  // Plotly writes the numbers of the hover texts (%{y:.1f}) with the layout's separators, and a point
  // where there are none (GH-2971)
  it.each([
    ['en', /^\.,$/],
    ['de', /^,\.$/],
    ['fr', /^,\s$/],
    ['pl', /^,\s$/],
  ])('draws the chart with the separators of %s', async (language, separators) => {
    await inLanguage(language)
    await showMeteogram()
    expect(layoutDrawn().separators).toMatch(separators)
  })

  // the chart's own day labels, above the panels
  it.each([
    ['en', '15/10'],
    ['de', '15.10.'],
    ['fr', '15/10'],
    ['cs', '15. 10.'],
  ])('writes the day labels of the chart in %s as %s', async (language, expected) => {
    await inLanguage(language)
    await showMeteogram()
    const [, , layout] = plotly.newPlot.mock.lastCall as unknown as [unknown, unknown, { annotations: { text: string }[] }]
    expect(layout.annotations.some(annotation => annotation.text.replace(/<\/?b>/g, '').endsWith(` ${expected}`))).toBe(true)
  })

  // Thursday the 15th: the weekday of the chart's day labels and of the compact view's day cards, and
  // the Plotly language of the hover heading, which Plotly writes itself (GH-3051). The code is the
  // app's, the language the tag it stands for (nuxt.config.ts)
  const thursdays = [
    ['en', 'en-GB', 'Thu', '%a %d/%m %H:%M'],
    ['de', 'de-DE', 'Do', '%a %d.%m. %H:%M'],
    ['de-hh', 'de-DE', 'Do', '%a %d.%m. %H:%M'],
    ['fr', 'fr-FR', 'jeu.', '%a %d/%m %H:%M'],
    ['es', 'es-ES', 'jue', '%a %d/%m %H:%M'],
    ['it', 'it-IT', 'gio', '%a %d/%m %H:%M'],
    ['nl', 'nl-NL', 'do', '%a %d-%m %H:%M'],
    ['pl', 'pl-PL', 'czw.', '%a %d.%m %H:%M'],
    ['cs', 'cs-CZ', 'čt', '%a %d. %m. %H:%M'],
    ['da', 'da-DK', 'tors.', '%a %d.%m %H:%M'],
    ['lb', 'lb-LU', 'Don', '%a %d.%m. %H:%M'],
  ] as const

  it.each(thursdays)('names the weekday of the day labels in %s (%s) %s', async (code, _language, weekday) => {
    await inLanguage(code)
    await showMeteogram()
    const [, , layout] = plotly.newPlot.mock.lastCall as unknown as [unknown, unknown, { annotations: { text: string }[] }]
    expect(layout.annotations.some(annotation => annotation.text.startsWith(`<b>${weekday}</b>`))).toBe(true)
  })

  // Chrome has no data for Luxembourgish and would write the system's language (GH-2971): German is written
  it('names the weekday of the day labels in German where the browser has no data for Luxembourgish', async () => {
    const supported = Intl.DateTimeFormat.supportedLocalesOf.bind(Intl.DateTimeFormat)
    vi.spyOn(Intl.DateTimeFormat, 'supportedLocalesOf').mockImplementation((languages, options) =>
      supported(languages, options).filter(language => !String(language).startsWith('lb')))
    onTestFinished(() => {
      vi.restoreAllMocks()
    })
    await inLanguage('lb')
    await showMeteogram()
    const [, , layout, config] = plotly.newPlot.mock.lastCall as unknown as [unknown, unknown, { annotations: { text: string }[] }, { locales: Record<string, { format: { shortDays: string[] } }> }]
    expect(layout.annotations.some(annotation => annotation.text.startsWith('<b>Do</b>'))).toBe(true)
    expect(config.locales['lb-LU']!.format.shortDays[4]).toBe('Do')
  })

  it.each(thursdays)('names the weekday of the day cards in %s (%s) %s', async (code, _language, weekday) => {
    await inLanguage(code)
    await showMeteogram()
    await showCompact()
    const cards = [...document.body.querySelectorAll('div')].filter(div => div.childElementCount === 0).map(div => div.textContent?.trim())
    expect(cards).toContain(weekday)
  })

  it.each(thursdays)('gives Plotly the language of the hover heading in %s (%s)', async (code, language, weekday, hoverformat) => {
    await inLanguage(code)
    await showMeteogram()
    const [, , layout, config] = plotly.newPlot.mock.lastCall as unknown as [unknown, unknown, { xaxis: { hoverformat: string } }, { locale: string, locales: Record<string, { format: { shortDays: string[] } }> }]
    expect(layout.xaxis.hoverformat).toBe(hoverformat)
    expect(config.locale).toBe(language)
    // Sunday first, as Plotly has it
    expect(config.locales[language]!.format.shortDays[4]).toBe(weekday)
  })

  it('draws the chart again in the language it is switched to', async () => {
    await showMeteogram()
    expect(layoutDrawn().separators).toBe('.,')

    await inLanguage('de')
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(2))
    expect(layoutDrawn().separators).toBe(',.')
  })

  // the compact view's day cards, which write the date by hand
  it.each([
    ['en', '15/10'],
    ['de', '15.10.'],
    ['fr', '15/10'],
    ['nl', '15-10'],
    ['pl', '15.10'],
    ['cs', '15. 10.'],
  ])('writes the day of the compact view in %s as %s', async (language, expected) => {
    await inLanguage(language)
    await showMeteogram()
    await showCompact()

    // the card's date is a text of its own, a line below the weekday
    const dates = [...document.body.querySelectorAll('div')].filter(div => div.childElementCount === 0).map(div => div.textContent?.trim())
    expect(dates).toContain(expected)
    // not the fixed `dd.MM` it was written in, whatever the language
    if (['en', 'fr', 'nl', 'cs'].includes(language))
      expect(wrapper!.text()).not.toContain('15.10')
    // the rain, 24 times 0.25 mm, with the language's decimal separator
    expect(wrapper!.text()).toContain(language === 'en' ? '6.0 mm' : '6,0 mm')
  })
})

describe('meteogram display synced to the URL', { timeout: 15_000 }, () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  const unhandled: unknown[] = []
  const record = (reason: unknown) => unhandled.push(reason)

  afterEach(() => {
    process.off('unhandledRejection', record)
    unhandled.length = 0
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // a navigation that fails -- one a guard redirects, or a newer one supersedes -- rejects `router.replace`;
  // the pages that sync to the URL catch it, and the meteogram's own horizon, panels and compact view must too
  it.each([
    ['the horizon', (vm: any) => { vm.horizonHours = 24 }, { horizon: '24' }],
    ['the panels', (vm: any) => { vm.visiblePanels = { ...vm.visiblePanels, wind: false } }, { panels: 'temp,precip,cloud,pressure' }],
    ['the compact view', (vm: any) => { vm.compact = true }, { compact: 'true' }],
  ])('leaves no unhandled rejection where a failed navigation follows a change of %s', async (_what, change, query) => {
    plotly.newPlot.mockClear()
    wrapper = await mountSuspended(Meteogram, { props: { values, stationName: 'Berlin' }, attachTo: document.body })
    // swapped in by hand: a spy keeps a handler on the promise it returns, which would hide an unhandled rejection
    const router = useRouter()
    const replaced: unknown[] = []
    const { replace } = router
    router.replace = (async (to: unknown) => {
      replaced.push(to)
      throw new Error('navigation aborted')
    }) as typeof router.replace
    onTestFinished(() => {
      router.replace = replace
    })
    process.on('unhandledRejection', record)

    change(wrapper.vm)
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))

    expect(replaced).toHaveLength(1)
    expect(replaced[0]).toMatchObject({ query })
    expect(unhandled).toEqual([])
  })
})

describe('meteogram text alternative', { timeout: 15_000 }, () => {
  // 30 hourly values of the series the panels plot; the cloud cover as the backend gives it, a fraction
  const hours = 30
  const forecast = Object.entries({
    temperature_air_2m: (hour: number) => 10 + hour / 10,
    wind_speed: (hour: number) => 4 + hour / 10,
    wind_direction: () => 270,
    precipitation_amount_significant_weather_last_1h: (hour: number) => hour === 1 ? 0.5 : 0,
    cloud_cover_total: () => 0.5,
    pressure_air_sea_level: () => 1013.25,
  }).flatMap(([parameter, curve]) => Array.from({ length: hours }, (_, hour) => ({
    station_id: '10384',
    resolution: 'hourly',
    dataset: 'small',
    parameter,
    timestamp: new Date(Date.UTC(2026, 9, 1, hour)).toISOString().replace('.000Z', '+00:00'),
    value: curve(hour),
    quality_flags: null,
  })))

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  async function showForecast(route = '/meteogram', props: Record<string, unknown> = {}) {
    wrapper = await mountSuspended(Meteogram, { props: { values: forecast, stationName: 'Berlin', ...props }, attachTo: document.body, route })
    return wrapper.vm as any
  }
  const figure = () => document.body.querySelector('[role="figure"]')!
  const toggle = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Show as table')
  async function openTable() {
    toggle()!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    return document.body.querySelector('table')!
  }
  const headers = (table: Element) => [...table.querySelectorAll('thead th')].map(th => th.textContent?.trim())
  const rows = (table: Element) => [...table.querySelectorAll('tbody tr')].map(row => [...row.children].map(cell => cell.textContent?.trim()))

  it('describes the figure by the span of the forecast and its temperatures', async () => {
    await showForecast()
    const description = document.getElementById(figure().getAttribute('aria-describedby')!)
    expect(description?.textContent?.trim()).toBe(
      'Forecast from 01/10/2026, 00:00 to 02/10/2026, 05:00. Temperature from 10.0 to 12.9 °C. The values are in the table below the chart.',
    )
  })

  it('offers the values of the plotted series as a table behind a button that says whether it is open', async () => {
    await showForecast()
    expect(document.body.querySelector('table')).toBeNull()
    expect(toggle()?.getAttribute('aria-expanded')).toBe('false')

    const table = await openTable()
    expect(toggle()?.getAttribute('aria-expanded')).toBe('true')
    expect(headers(table)).toEqual([
      'Time (UTC)',
      'Temperature °C',
      'Wind m/s',
      'Direction °',
      'Precipitation mm',
      'Total Cloud Cover %',
      'Pressure hPa',
    ])
    expect(rows(table)).toHaveLength(hours)
    // each time is the header of its row; the cloud cover is in percent, as the chart has it
    expect(rows(table)[1]).toEqual(['01/10/2026, 01:00', '10.1', '4.1', '270', '0.50', '50', '1,013.3'])
    expect(table.querySelector('caption')?.textContent?.trim()).toBe('Forecast chart for Berlin')
    expect(table.querySelector('tbody tr')?.firstElementChild?.tagName).toBe('TH')
  })

  it('writes the times in the station\'s time zone', async () => {
    await showForecast('/meteogram', { stationCoords: { latitude: 52.52, longitude: 13.4 } })
    const table = await openTable()
    expect(headers(table)[0]).toBe('Time (Europe/Berlin)')
    // midnight UTC is two o'clock in Berlin in October, on summer time
    expect(rows(table)[0]![0]).toBe('01/10/2026, 02:00')
  })

  it('leaves out the columns of a panel that is switched off, and the rows beyond the horizon', async () => {
    const vm = await showForecast()
    vm.visiblePanels = { ...vm.visiblePanels, wind: false, cloud: false, pressure: false, precip: false }
    vm.horizonHours = 24
    await nextTick()
    const table = await openTable()
    expect(headers(table)).toEqual(['Time (UTC)', 'Temperature °C'])
    // from the first hour to the 24th after it
    expect(rows(table)).toHaveLength(25)
  })

  it('has no table where the compact view shows day cards instead of the chart', async () => {
    await showForecast('/meteogram?compact=true')
    await vi.waitFor(() => expect(document.body.querySelector('[role="figure"]')).toBeNull())
    expect(toggle()).toBeUndefined()
    expect(document.body.querySelector('table')).toBeNull()
  })
})

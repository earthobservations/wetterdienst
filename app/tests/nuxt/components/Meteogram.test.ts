import process from 'node:process'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import tzLookup from 'tz-lookup'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import Meteogram from '~/components/Meteogram.vue'
import { panelToggleStyle, SERIES_LABEL, seriesLabelColor } from '~/utils/chart-theme'
import { chromeWithoutLuxembourgish } from '../../helpers/chrome-without-luxembourgish'

// ECharts draws in these tests as it does in a browser, to an SVG string, and every call is recorded: a test reads the
// option the component gave it, or what that option drew (`tests/helpers/ssr-echarts.ts`)
const echarts = vi.hoisted(() => ({ ssr: null as any }))
vi.mock('~/utils/echarts-loader', async () => {
  const { createSsrEcharts } = await import('../../helpers/ssr-echarts')
  echarts.ssr = createSsrEcharts()
  return { loadEcharts: () => echarts.ssr }
})
const ssr = () => echarts.ssr as ReturnType<typeof import('../../helpers/ssr-echarts').createSsrEcharts>
const clearDrawn = () => echarts.ssr?.clear()
/** The chart is drawn: once the code has loaded, which a busy runner can take a while over */
async function waitDrawn() {
  await vi.waitFor(() => expect(ssr().calls.setOption).toHaveBeenCalled(), { timeout: 5000 })
  await flushPromises()
}

// The zone lookup answers as the library does, until a test has it name a zone the browser does not know
vi.mock('tz-lookup', async (importOriginal) => {
  const original = await importOriginal<{ default: (latitude: number, longitude: number) => string }>()
  return { default: vi.fn(original.default) }
})

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
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: [...values, ...clouds] })
    await waitDrawn()
    expect(ssr().option().series.map((series: { id: string }) => series.id)).toContain('cloudLow')
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
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Hamburg' }, attachTo: document.body })
    await wrapper.setProps({ values: rows })
    await waitDrawn()
    const series = (id: string) => ssr().option().series.find((s: { id: string }) => s.id === id) as { data: [number, number | null][] }
    const [mean, high, low] = [series('temp'), series('tempMax'), series('tempMin')]
    // an hour belongs to the window that ends at or after it, which a date's one point holds
    const boundAt = (bound: typeof high, hour: number) => bound.data.find(point => point[0] === hour)![1]!
    expect(mean.data).toHaveLength(temperature.length)
    for (const [hour, value] of mean.data) {
      expect(value!, `${new Date(hour).toISOString()} above its maximum`).toBeLessThanOrEqual(boundAt(high, hour))
      expect(value!, `${new Date(hour).toISOString()} below its minimum`).toBeGreaterThanOrEqual(boundAt(low, hour))
    }
    // as drawn between the stamps, 16.7 degrees at 14:00 was above the maximum line (14.1)
    expect(boundAt(high, Date.parse('2026-10-15T14:00:00Z'))).toBe(17.4)
    expect(boundAt(low, Date.parse('2026-10-15T14:00:00Z'))).toBe(8)
  })

  it('draws no band, and calls the curve the temperature, where the maximum and minimum hold no value', async () => {
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Hamburg' }, attachTo: document.body })
    await wrapper.setProps({ values: [...rows.filter(row => row.parameter === 'temperature_air_2m'), ...Object.entries(stamped).flatMap(([parameter, points]) => points.map(([timestamp]) => ({ ...values[0]!, parameter, timestamp, value: null })))] })
    await waitDrawn()
    const ids = ssr().option().series.map((series: { id: string }) => series.id)
    expect(ids).not.toContain('tempMax')
    expect(ids).not.toContain('tempMin')
    expect(ids).toContain('temp')
  })
})

describe('meteogram chart name', { timeout: 15_000 }, () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the figure the chart is drawn in, by the role and the name a screen reader announces it with
  async function drawnInto(stationName: string | null) {
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName }, attachTo: document.body })
    await wrapper.setProps({ values })
    await waitDrawn()
    const figure = document.body.querySelector('[role="figure"]')!
    return [figure.getAttribute('role'), figure.getAttribute('aria-label')]
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
  // the morning of the 14th: the day of the values is a day ahead, as the day cards start at today (GH-3840)
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-14T08:00:00Z') })
  })
  afterEach(async () => {
    vi.useRealTimers()
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
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: [...day, ...rain] })
    await waitDrawn()
  }

  // The compact view, which the Meteogram also writes to the URL (`?view=compact`) with a navigation of
  // the router. That navigation runs on after the test, and a test that ends before it has finished
  // leaves it to the teardown of the test's document, where its `history` is gone (GH-3064): wait for
  // the URL.
  async function showCompact() {
    ;(wrapper!.vm as any).view = 'compact'
    await wrapper!.vm.$nextTick()
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.view).toBe('compact'))
  }

  // the numbers of the axes, written with the language's separators, and a point where there are none (GH-2971)
  const formatted = () => ssr().option().yAxis[1].axisLabel.formatter(2.5)

  it.each([
    ['en', '2.5'],
    ['de', '2,5'],
    ['fr', '2,5'],
    ['pl', '2,5'],
  ])('writes the numbers of the axes in %s as %s', async (language, expected) => {
    await inLanguage(language)
    await showMeteogram()
    expect(formatted()).toBe(expected)
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
    expect(ssr().texts().some(text => text.endsWith(` ${expected}`))).toBe(true)
  })

  // the hour of the time axis, as the language writes a time of day: Danish writes a point, not a colon, between the
  // hour and the minute, and Luxembourgish is written as German where the browser has no data for it (GH-4007)
  const axisHours = () => ssr().texts().filter(text => /^\d{2}[:.]\d{2}$/.test(text))

  it.each([
    ['en', ':'],
    ['de', ':'],
    ['de-hh', ':'],
    ['lb', ':'],
    ['da', '.'],
  ])('writes the hours of the time axis in %s with "%s" between the hour and the minute', async (code, separator) => {
    await inLanguage(code)
    await showMeteogram()
    const hours = axisHours()
    expect(hours.length).toBeGreaterThan(2)
    for (const hour of hours)
      expect(hour).toMatch(new RegExp(`^\\d{2}\\${separator}00$`))
  })

  // Node has the data for Luxembourgish that Chrome lacks (GH-4007): `chromeWithoutLuxembourgish` writes English for
  // any `lb` handed to Intl, and says what was handed over. The chart's hours are the same text in German and in
  // English, so that no `lb` was handed to Intl is what shows the stand-in at work
  function inChromeWithoutLuxembourgish() {
    const chrome = chromeWithoutLuxembourgish()
    onTestFinished(chrome.restore)
    return chrome
  }
  const luxembourgish = (chrome: { passed: string[] }) => chrome.passed.filter(language => /^lb/i.test(language))

  it('writes the hours of the time axis of Luxembourgish as German where the browser has no data for it', async () => {
    await inLanguage('lb')
    const chrome = inChromeWithoutLuxembourgish()
    await showMeteogram()
    expect(axisHours()).toContain('06:00')
    expect(chrome.passed).toContain('de-LU')
    expect(luxembourgish(chrome)).toEqual([])
  })

  it('writes the times of the data table of Luxembourgish as German where the browser has no data for it', async () => {
    await inLanguage('lb')
    const chrome = inChromeWithoutLuxembourgish()
    await showMeteogram()
    ;(wrapper!.vm as any).view = 'table'
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.view).toBe('table'))
    // the 15th of October at midnight, German's order; English would write "10/15/2026, 12:00 AM"
    expect(document.body.querySelector('tbody th')?.textContent?.trim()).toBe('15.10.2026, 00:00')
    expect(luxembourgish(chrome)).toEqual([])
  })

  // a zone the browser does not know made every date of the chart invalid: "Invalid DateTime" in the day labels and
  // "UTC+NaN:NaN" in the toolbar. The zone is checked once, and the station is written in UTC
  it('draws the chart in UTC where the browser does not know the station\'s time zone', async () => {
    vi.mocked(tzLookup).mockReturnValue('Mars/Olympus')
    // back to the library's own answer, which `vi.fn(original)` below keeps as its implementation
    onTestFinished(() => {
      vi.mocked(tzLookup).mockReset()
    })
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin', stationCoords: { latitude: 52.47, longitude: 13.4 } }, attachTo: document.body })
    await wrapper.setProps({ values: [...day, ...rain] })
    await waitDrawn()
    expect(ssr().texts().join(' ')).not.toContain('Invalid')
    expect(axisHours()).toContain('06:00')
    expect(document.body.textContent).not.toMatch(/NaN|Invalid/)
    expect(document.body.textContent).toContain('UTC (UTC+00:00)')
  })

  // Thursday the 15th: the weekday of the chart's day labels and of the compact view's day cards. The code is the
  // app's, the language the tag it stands for (nuxt.config.ts)
  const thursdays = [
    ['en', 'en-GB', 'Thu'],
    ['de', 'de-DE', 'Do'],
    ['de-hh', 'de-DE', 'Do'],
    ['fr', 'fr-FR', 'jeu.'],
    ['es', 'es-ES', 'jue'],
    ['it', 'it-IT', 'gio'],
    ['nl', 'nl-NL', 'do'],
    ['pl', 'pl-PL', 'czw.'],
    ['cs', 'cs-CZ', 'čt'],
    ['da', 'da-DK', 'tors.'],
    ['lb', 'lb-LU', 'Don'],
  ] as const

  it.each(thursdays)('names the weekday of the day labels in %s (%s) %s', async (code, _language, weekday) => {
    await inLanguage(code)
    await showMeteogram()
    expect(ssr().texts().some(text => text.startsWith(`${weekday} `))).toBe(true)
  })

  // Chrome has no data for Luxembourgish and would write the system's language (GH-2971): German is written
  it('names the weekday of the day labels in German where the browser has no data for Luxembourgish', async () => {
    await inLanguage('lb')
    const chrome = inChromeWithoutLuxembourgish()
    await showMeteogram()
    // English would write "Thu"
    expect(ssr().texts().some(text => text.startsWith('Do '))).toBe(true)
    expect(luxembourgish(chrome)).toEqual([])
  })

  it.each(thursdays)('names the weekday of the day cards in %s (%s) %s', async (code, _language, weekday) => {
    await inLanguage(code)
    await showMeteogram()
    await showCompact()
    const cards = [...document.body.querySelectorAll('div')].filter(div => div.childElementCount === 0).map(div => div.textContent?.trim())
    expect(cards).toContain(weekday)
  })

  it('names the series of the y axes in colours that read on the paper (GH-3618)', async () => {
    await showMeteogram()
    // the panels the values have: the rain, the temperature
    const { yAxis } = ssr().option()
    const expected = { 1: 'blue', 2: 'red' } as const
    for (const [index, series] of Object.entries(expected)) {
      expect(yAxis[Number(index)].axisLabel.color, `axis ${index}`).toBe(SERIES_LABEL[series].light)
      // the titles are drawn by the chart's own series, top panel first: the rain, then the temperature
      expect(ssr().axisTitles()[Number(index) - 1]!.fill, `title ${index}`).toBe(SERIES_LABEL[series].light)
    }
  })

  it('writes the label of a weekend day in a red that reads on the paper, and the others in the text colour (GH-3618)', async () => {
    clearDrawn()
    // Thursday the 15th and Saturday the 17th
    const saturday = day.map(value => ({ ...value, timestamp: value.timestamp.replace('-15T', '-17T') }))
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: [...day, ...saturday] })
    await waitDrawn()
    const colourOf = (label: string) => new RegExp(`<text[^>]*fill="([^"]*)"[^>]*>${label}`).exec(ssr().svg())?.[1]
    expect(colourOf('Sat 17/10')).toBe(SERIES_LABEL.red.light)
    expect(colourOf('Thu 15/10')).toBeDefined()
    expect(colourOf('Thu 15/10')).not.toBe(SERIES_LABEL.red.light)
  })

  it('disposes its chart where it goes (GH-3619)', async () => {
    await showMeteogram()
    ssr().calls.dispose.mockClear()
    wrapper!.unmount()
    wrapper = undefined
    expect(ssr().calls.dispose).toHaveBeenCalled()
  })

  it('draws the chart again in the language it is switched to', async () => {
    await showMeteogram()
    expect(formatted()).toBe('2.5')

    await inLanguage('de')
    await vi.waitFor(() => expect(formatted()).toBe('2,5'))
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

  // the 14th from 18:00 to the 16th 05:00 UTC: a stub of yesterday above today, and a last day of six hours
  it('lists no card for the day before today, and marks the last day as partial with its hours (GH-3840)', async () => {
    const hours = Array.from({ length: 36 }, (_, hour) => ({
      ...day[0]!,
      timestamp: new Date(Date.UTC(2026, 9, 14, 18 + hour)).toISOString(),
      value: 10,
    }))
    vi.setSystemTime(new Date('2026-10-15T08:00:00Z'))
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: hours })
    await waitDrawn()
    await showCompact()
    const cards = [...document.body.querySelectorAll('.rounded-2xl')].map(card => card.textContent ?? '')
    expect(cards).toHaveLength(2)
    expect(cards[0]).toMatch(/today/i)
    expect(cards[0]).toContain('15/10')
    expect(cards[0]).not.toContain('partial')
    expect(cards[1]).toContain('16/10')
    expect(cards[1]).toContain('partial, 6 h')
    expect(cards.some(card => card.includes('14/10'))).toBe(false)
  })

  it('says there is no data in place of the cards where every day of the run is before today (GH-3840)', async () => {
    vi.setSystemTime(new Date('2026-10-20T08:00:00Z'))
    await showMeteogram()
    await showCompact()
    expect(document.body.querySelectorAll('.rounded-2xl')).toHaveLength(0)
    expect(wrapper!.text()).toContain('No data available for the selected query')
  })

  // the weather of a day card is an icon, which a screen reader does not read: the words are in the
  // card, and the icon is hidden from it (WCAG 1.1.1). `iconsOf` are the Phosphor icons drawn for the weather
  // of the cards, by the name the icon component is given (GH-3527)
  const iconsOf = () => [...document.body.querySelectorAll('[data-weather]')].map(node => node.getAttribute('data-weather'))
  const hiddenIconsOf = () => [...document.body.querySelectorAll('[data-weather][aria-hidden="true"]')]
  const wordsOf = () => [...document.body.querySelectorAll('.sr-only')].map(node => node.textContent?.trim())

  it('gives the icon of a day card a text alternative, and hides the icon, where no weather code is served', async () => {
    await showMeteogram()
    await showCompact()
    // 6 mm of rain over 10 to 16 degrees and no weather code: the heuristic's rain
    expect(iconsOf()).toContain('rain')
    expect(hiddenIconsOf().length).toBe(iconsOf().length)
    expect(wordsOf()).toContain('Rain')
    // and the drop before the rain's amount is a decoration with the word for it beside
    expect(document.body.querySelector('[aria-hidden="true"][class~="i-ph:drop"]')).not.toBeNull()
    expect(wordsOf()).toContain('Precipitation:')
    // the space after the colon is in the text a screen reader gets ("Precipitation: 3.2 mm"), not trimmed off by the template
    const precipitation = [...document.body.querySelectorAll('.sr-only')].filter(node => node.textContent?.includes('Precipitation'))
    expect(precipitation.length).toBeGreaterThan(0)
    expect(precipitation.map(node => node.textContent!.endsWith(': '))).not.toContain(false)
  })

  // three days, each with the weather code of its hours: rain (61), a thunderstorm (95), clear sky (0)
  it.each([
    [61, 'rain', 'i-ph:cloud-rain', 'Rain'],
    [95, 'thunderstorm', 'i-ph:cloud-lightning', 'Thunderstorm'],
    [0, 'clear', 'i-ph:sun', 'Sunny'],
    [2, 'partlyCloudy', 'i-ph:cloud-sun', 'Partly cloudy'],
    [3, 'cloudy', 'i-ph:cloud', 'Cloudy'],
    [18, 'wind', 'i-ph:wind', 'Windy'],
    [20, 'drizzle', 'i-ph:drop-half', 'Drizzle'],
    [53, 'drizzle', 'i-ph:drop-half', 'Drizzle'],
    [71, 'snow', 'i-ph:cloud-snow', 'Snow'],
    [45, 'fog', 'i-ph:cloud-fog', 'Fog'],
    // dust and snow storms are no thunderstorms (30-39 were drawn as one)
    [33, 'dust', 'i-ph:wind', 'Dust or sand storm'],
    [38, 'blowingSnow', 'i-ph:snowflake', 'Blowing snow'],
    [69, 'sleet', 'i-ph:cloud-snow', 'Sleet'],
    // a funnel cloud is a tornado or a waterspout, not a sunny day (GH-3965)
    [19, 'funnelCloud', 'i-ph:tornado', 'Funnel cloud'],
  ])('names the weather of weather code %i as %s (icon %s, words %s) in a day card', async (code, kind, icon, words) => {
    const coded = day.map(value => ({ ...value, parameter: 'weather_significant', value: code }))
    clearDrawn()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: [...day, ...coded] })
    await waitDrawn()
    await showCompact()
    expect(iconsOf()).toContain(kind)
    // the icon drawn is the Phosphor icon of the kind, hidden from a screen reader, which reads the words
    const drawn = [...document.body.querySelectorAll(`[data-weather="${kind}"]`)]
    expect(drawn.length).toBeGreaterThan(0)
    for (const node of drawn) {
      expect(node.getAttribute('aria-hidden')).toBe('true')
      expect(node.classList.contains(icon)).toBe(true)
    }
    expect(wordsOf()).toContain(words)
    expect(document.body.textContent).not.toMatch(/\p{Extended_Pictographic}/u)
  })

  // in every language, in its own word for the rain
  it.each([
    ['en', 'Rain'],
    ['de', 'Regen'],
    ['de-hh', 'Regen'],
    ['fr', 'Pluie'],
    ['es', 'Lluvia'],
    ['it', 'Pioggia'],
    ['nl', 'Regen'],
    ['pl', 'Deszcz'],
    ['cs', 'Déšť'],
    ['da', 'Regn'],
    ['lb', 'Reen'],
  ])('names the weather of a day card in %s as %s', async (code, rain) => {
    await inLanguage(code)
    await showMeteogram()
    await showCompact()
    expect(wordsOf()).toContain(rain)
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
    ['the view', (vm: any) => { vm.view = 'table' }, { view: 'table' }],
  ])('leaves no unhandled rejection where a failed navigation follows a change of %s', async (_what, change, query) => {
    clearDrawn()
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
  // 30 hourly values of the series the panels plot; the cloud cover in percent, the unit the app settings start from
  const hours = 30
  const forecast = Object.entries({
    temperature_air_2m: (hour: number) => 10 + hour / 10,
    wind_speed: (hour: number) => 4 + hour / 10,
    wind_direction: () => 270,
    precipitation_amount_significant_weather_last_1h: (hour: number) => hour === 1 ? 0.5 : 0,
    cloud_cover_total: () => 50,
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
  beforeEach(() => {
    // the first of October, which the values start on: the day cards start at today (GH-3840)
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-01T06:00:00Z') })
  })
  afterEach(async () => {
    vi.useRealTimers()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
    // the URL back to none, which the next test's chart would read its view from
    await useRouter().replace({ query: {} })
  })

  async function showForecast(route = '/meteogram', props: Record<string, unknown> = {}) {
    wrapper = await mountSuspended(Meteogram, { props: { values: forecast, stationName: 'Berlin', ...props }, attachTo: document.body, route })
    return wrapper.vm as any
  }
  const figure = () => document.body.querySelector('[role="figure"]')
  const disclosure = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Show as table')
  const radios = () => [...document.body.querySelectorAll<HTMLButtonElement>('[role="radiogroup"] [role="radio"]')]
  const radio = (name: string) => radios().find(button => button.textContent?.trim() === name)!
  const checked = () => radios().filter(button => button.getAttribute('aria-checked') === 'true').map(button => button.textContent?.trim())
  const days = () => document.body.querySelector('.animate-bounce-slow')
  async function showTable() {
    radio('Table').click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    return document.body.querySelector('table')!
  }
  const headers = (table: Element) => [...table.querySelectorAll('thead th')].map(th => th.textContent?.trim())
  const rows = (table: Element) => [...table.querySelectorAll('tbody tr')].map(row => [...row.children].map(cell => cell.textContent?.trim()))
  const summary = () => document.getElementById(figure()!.getAttribute('aria-describedby')!.split(' ')[0]!)?.textContent?.trim()
  const press = async (button: Element, key: string) => {
    button.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
    await nextTick()
  }

  it('describes the figure by the span of the forecast and its temperatures, and says where the values are', async () => {
    await showForecast()
    expect(summary()).toBe(
      'Forecast from 01/10/2026, 00:00 to 02/10/2026, 05:00. Temperature from 10.0 to 12.9 °C. The values are in the table view, which you choose above the chart.',
    )
  })

  it('offers the chart, the compact overview and the table as one radio group, with the chart chosen', async () => {
    await showForecast()
    const group = document.body.querySelector('[role="radiogroup"]')!
    expect(group.getAttribute('aria-label')).toBe('View')
    expect(radios().map(button => button.textContent?.trim())).toEqual(['Chart', 'Compact', 'Table'])
    expect(checked()).toEqual(['Chart'])
    // one stop in the tab order: the chosen option
    expect(radios().map(button => button.tabIndex)).toEqual([0, -1, -1])
  })

  it('has no table under the chart, and no "Show as table" disclosure, in the chart view', async () => {
    await showForecast()
    expect(figure()).not.toBeNull()
    expect(document.body.querySelector('table')).toBeNull()
    expect(disclosure()).toBeUndefined()
  })

  it('switches between the chart, the day cards and the table, and shows no chart in the table view', async () => {
    clearDrawn()
    await showForecast()

    radio('Table').click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    expect(checked()).toEqual(['Table'])
    expect(figure()).toBeNull()
    expect(days()).toBeNull()

    radio('Compact').click()
    await vi.waitFor(() => expect(days()).not.toBeNull())
    expect(checked()).toEqual(['Compact'])
    expect(figure()).toBeNull()
    expect(document.body.querySelector('table')).toBeNull()

    // back to the chart: drawn again
    radio('Chart').click()
    await vi.waitFor(() => expect(figure()).not.toBeNull())
    await waitDrawn()
    expect(checked()).toEqual(['Chart'])
    expect(document.body.querySelector('table')).toBeNull()
  })

  it('writes the values of the plotted series as a table of its own, with the caption, the scopes and a box the keys scroll', async () => {
    await showForecast()
    const table = await showTable()
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
    // each time is the header of its row
    expect(rows(table)[1]).toEqual(['01/10/2026, 01:00', '10.1', '4.1', '270', '0.50', '50', '1,013.3'])
    expect(table.querySelector('caption')?.textContent?.trim()).toBe('Forecast chart for Berlin')
    expect(table.querySelector('tbody tr')?.firstElementChild?.tagName).toBe('TH')
    expect([...table.querySelectorAll('thead th')].every(th => th.getAttribute('scope') === 'col')).toBe(true)
    expect(table.querySelector('tbody th')?.getAttribute('scope')).toBe('row')
    // the box that scrolls is in the tab order and named; it is no longer capped at the disclosure's height
    const region = document.body.querySelector('[role="region"]')!
    expect(region.getAttribute('tabindex')).toBe('0')
    expect(region.getAttribute('aria-label')).toBe('Forecast chart for Berlin')
    expect(region.className).not.toContain('max-h-96')
  })

  it('keeps the header and the time column in view while the table scrolls', async () => {
    await showForecast()
    const table = await showTable()
    expect([...table.querySelectorAll('thead th')].every(th => th.classList.contains('sticky') && th.classList.contains('top-0'))).toBe(true)
    expect(table.querySelector('thead th')?.classList.contains('left-0')).toBe(true)
    expect([...table.querySelectorAll('tbody th')].every(th => th.classList.contains('sticky') && th.classList.contains('left-0'))).toBe(true)
  })

  it('shows the table the values the figure is described by', async () => {
    await showForecast()
    const [, from, to, min, max] = summary()!.match(/from (.+?) to (.+?)\. Temperature from (.+?) to (.+?) °C/)!
    const table = await showTable()
    const all = rows(table)
    expect(all[0]![0]).toBe(from)
    expect(all.at(-1)![0]).toBe(to)
    const temperatures = all.map(row => Number(row[1]))
    expect(Math.min(...temperatures).toFixed(1)).toBe(min)
    expect(Math.max(...temperatures).toFixed(1)).toBe(max)
  })

  it('writes the times in the station\'s time zone', async () => {
    await showForecast('/meteogram', { stationCoords: { latitude: 52.52, longitude: 13.4 } })
    const table = await showTable()
    expect(headers(table)[0]).toBe('Time (Europe/Berlin)')
    // midnight UTC is two o'clock in Berlin in October, on summer time
    expect(rows(table)[0]![0]).toBe('01/10/2026, 02:00')
  })

  it('leaves out the columns of a panel that is switched off, and the rows beyond the horizon', async () => {
    const vm = await showForecast()
    vm.visiblePanels = { ...vm.visiblePanels, wind: false, cloud: false, pressure: false, precip: false }
    vm.horizonHours = 24
    await nextTick()
    const table = await showTable()
    expect(headers(table)).toEqual(['Time (UTC)', 'Temperature °C'])
    // from the first hour to the 24th after it
    expect(rows(table)).toHaveLength(25)
  })

  it('keeps the panel toggles and the horizon in the table view, as they choose its columns and rows', async () => {
    await showForecast()
    await showTable()
    expect(document.body.querySelector('button[title="Wind"]')).not.toBeNull()
    expect([...document.body.querySelectorAll('button')].some(button => button.textContent?.trim() === '24h')).toBe(true)
  })

  it('has no table where the compact view shows day cards instead of the chart', async () => {
    await showForecast('/meteogram?compact=true')
    await vi.waitFor(() => expect(figure()).toBeNull())
    expect(disclosure()).toBeUndefined()
    expect(document.body.querySelector('table')).toBeNull()
  })

  describe('the view as a choice', () => {
    it('writes the choice to the URL and to local storage', async () => {
      await showForecast()
      await showTable()
      await vi.waitFor(() => expect(useRouter().currentRoute.value.query.view).toBe('table'))
      expect(localStorage.getItem('meteogram.view')).toBe('table')

      radio('Compact').click()
      await vi.waitFor(() => expect(useRouter().currentRoute.value.query.view).toBe('compact'))
      expect(localStorage.getItem('meteogram.view')).toBe('compact')
    })

    it('opens the view a link names, whatever local storage holds', async () => {
      await showForecast('/meteogram?view=table')
      expect(checked()).toEqual(['Table'])
      expect(document.body.querySelector('table')).not.toBeNull()
      expect(figure()).toBeNull()
      wrapper!.unmount()

      localStorage.setItem('meteogram.view', 'compact')
      await showForecast('/meteogram?view=chart')
      expect(checked()).toEqual(['Chart'])
      expect(figure()).not.toBeNull()
    })

    it('opens the table from a link made of the choice, once it is in the URL', async () => {
      await showForecast()
      await showTable()
      await vi.waitFor(() => expect(useRouter().currentRoute.value.query.view).toBe('table'))
      const link = useRouter().currentRoute.value.fullPath
      expect(link).toContain('view=table')
      wrapper!.unmount()
      localStorage.clear()

      await showForecast(link)
      expect(checked()).toEqual(['Table'])
      expect(document.body.querySelector('table')).not.toBeNull()
    })

    it('opens the compact overview for the links of the time the compact view was a toggle', async () => {
      await showForecast('/meteogram?compact=true')
      expect(checked()).toEqual(['Compact'])
      wrapper!.unmount()

      await showForecast('/meteogram?compact=1')
      expect(checked()).toEqual(['Compact'])
      wrapper!.unmount()

      localStorage.setItem('meteogram.view', 'compact')
      await showForecast('/meteogram?compact=false')
      expect(checked()).toEqual(['Chart'])
      wrapper!.unmount()

      // one parameter wins: the new one
      await showForecast('/meteogram?compact=true&view=table')
      expect(checked()).toEqual(['Table'])
    })

    it('takes the link\'s view over and writes it as `view` alone, without the old parameter', async () => {
      await showForecast('/meteogram?compact=true')
      radio('Table').click()
      await vi.waitFor(() => expect(useRouter().currentRoute.value.query.view).toBe('table'))
      expect(useRouter().currentRoute.value.query.compact).toBeUndefined()
    })

    it('remembers the view across a reload', async () => {
      await showForecast()
      await showTable()
      wrapper!.unmount()
      await useRouter().replace({ query: {} })

      await showForecast()
      expect(checked()).toEqual(['Table'])
      expect(document.body.querySelector('table')).not.toBeNull()
    })

    it('does not remember a view that a link or a small screen chose, only the reader\'s choice', async () => {
      await showForecast('/meteogram?view=table')
      expect(localStorage.getItem('meteogram.view')).toBeNull()
    })

    it('ignores a stored value that names no view', async () => {
      localStorage.setItem('meteogram.view', 'sunny')
      await showForecast()
      expect(checked()).toEqual(['Chart'])
    })

    it.each([
      ['true', 'Compact', 'compact'],
      ['false', 'Chart', 'chart'],
    ])('takes over once what the old key stored (%s) as the view %s, and removes the old key', async (old, name, stored) => {
      localStorage.setItem('meteogram.compact', old)
      await showForecast()
      expect(checked()).toEqual([name])
      expect(localStorage.getItem('meteogram.view')).toBe(stored)
      expect(localStorage.getItem('meteogram.compact')).toBeNull()
    })

    it('prefers the new key to the old one', async () => {
      localStorage.setItem('meteogram.view', 'table')
      localStorage.setItem('meteogram.compact', 'true')
      await showForecast()
      expect(checked()).toEqual(['Table'])
    })

    it('shows the compact overview on a small screen where nothing is stored or linked', async () => {
      // the view is chosen by a media query in rem (GH-3518), so a reader with a larger text size gets it sooner
      const original = window.matchMedia
      window.matchMedia = ((query: string) => ({
        matches: query === '(max-width: 40rem)',
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        onchange: null,
        dispatchEvent: () => false,
      })) as typeof window.matchMedia
      try {
        await showForecast()
        expect(checked()).toEqual(['Compact'])
      }
      finally {
        window.matchMedia = original
      }
    })
  })

  describe('by keyboard', () => {
    it('moves the choice and the focus with the arrow keys, round the ends, and with Home and End', async () => {
      await showForecast()
      radio('Chart').focus()

      await press(radio('Chart'), 'ArrowRight')
      expect(checked()).toEqual(['Compact'])
      expect(document.activeElement).toBe(radio('Compact'))
      expect(radios().map(button => button.tabIndex)).toEqual([-1, 0, -1])

      await press(radio('Compact'), 'ArrowDown')
      expect(checked()).toEqual(['Table'])
      expect(document.activeElement).toBe(radio('Table'))
      await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())

      // round the end
      await press(radio('Table'), 'ArrowRight')
      expect(checked()).toEqual(['Chart'])
      await press(radio('Chart'), 'ArrowLeft')
      expect(checked()).toEqual(['Table'])
      await press(radio('Table'), 'ArrowUp')
      expect(checked()).toEqual(['Compact'])

      await press(radio('Compact'), 'Home')
      expect(checked()).toEqual(['Chart'])
      await press(radio('Chart'), 'End')
      expect(checked()).toEqual(['Table'])
    })

    it('leaves the other keys alone', async () => {
      await showForecast()
      const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
      radio('Chart').dispatchEvent(event)
      expect(event.defaultPrevented).toBe(false)
      expect(checked()).toEqual(['Chart'])
      // and the arrow keys with a modifier are the browser's
      const history = new KeyboardEvent('keydown', { key: 'ArrowLeft', altKey: true, bubbles: true, cancelable: true })
      radio('Chart').dispatchEvent(history)
      expect(history.defaultPrevented).toBe(false)
      expect(checked()).toEqual(['Chart'])
    })
  })

  describe('as the widget', () => {
    it('has no view control, and keeps the table behind its button below the chart', async () => {
      await showForecast('/widget', { widget: true })
      expect(radios()).toEqual([])
      expect(figure()).not.toBeNull()
      expect(disclosure()?.getAttribute('aria-expanded')).toBe('false')
      expect(summary()).toContain('The values are in the table below the chart.')
      disclosure()!.click()
      await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    })

    it('shows the chart where the table was chosen on the page, and the day cards where those were', async () => {
      localStorage.setItem('meteogram.view', 'table')
      await showForecast('/widget', { widget: true })
      expect(figure()).not.toBeNull()
      wrapper!.unmount()

      localStorage.setItem('meteogram.view', 'compact')
      await showForecast('/widget', { widget: true })
      await vi.waitFor(() => expect(figure()).toBeNull())
      expect(days()).not.toBeNull()
    })

    it('takes over the old key as well', async () => {
      localStorage.setItem('meteogram.compact', 'true')
      await showForecast('/widget', { widget: true })
      await vi.waitFor(() => expect(figure()).toBeNull())
      expect(localStorage.getItem('meteogram.view')).toBe('compact')
    })
  })
})

// The Forecast's own chrome (GH-3642): the panel toggles say whether they are on and take the label colours of their
// series, the icons of the summary line take them too, and the card of today has an edge that reads (1.4.11).
describe('meteogram panel toggles, summary icons and today\'s card', { timeout: 15_000 }, () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    vi.useRealTimers()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  const SERIES = { temp: 'red', wind: 'cyan', precip: 'blue', cloud: 'slate', pressure: 'lime' } as const
  const toggles = () => [...document.body.querySelectorAll<HTMLButtonElement>('button[data-panel]')]
  /** The style attribute a style object comes to in this document, whatever it makes of a value it does not know */
  const styled = (style: Record<string, string>) => {
    const probe = document.createElement('span')
    Object.assign(probe.style, style)
    return probe.getAttribute('style')
  }

  it('has a toggle for each panel, each saying it is on, and a toggle that is on in the label colour of its series', async () => {
    wrapper = await mountSuspended(Meteogram, { props: { values, stationName: 'Berlin' }, attachTo: document.body })
    await flushPromises()
    expect(toggles().map(button => button.dataset.panel)).toEqual(Object.keys(SERIES))
    for (const button of toggles()) {
      expect(button.getAttribute('aria-pressed'), button.dataset.panel).toBe('true')
      expect(button.getAttribute('style'), button.dataset.panel).toBe(styled(panelToggleStyle(SERIES_LABEL[SERIES[button.dataset.panel as keyof typeof SERIES]].light)))
    }
  })

  it('says a toggle is off when it is switched off, and gives it back the greys of the app', async () => {
    wrapper = await mountSuspended(Meteogram, { props: { values, stationName: 'Berlin' }, attachTo: document.body })
    await flushPromises()
    const wind = toggles().find(button => button.dataset.panel === 'wind')!
    wind.click()
    await nextTick()
    expect(wind.getAttribute('aria-pressed')).toBe('false')
    expect(wind.getAttribute('style') ?? '').toBe('')
    expect(wind.className).toContain('text-gray-500')
  })

  // GH-3951: a toggle that is on differs from one that is off by shape (the filled icon), not by colour alone (1.4.1), and is
  // named by an aria-label of the same words as its title (4.1.2)
  it('draws the filled icon on a toggle that is on and the outline on one that is off, and only then', async () => {
    wrapper = await mountSuspended(Meteogram, { props: { values, stationName: 'Berlin' }, attachTo: document.body })
    await flushPromises()
    const icon = (button: HTMLElement) => button.querySelector('[class*="i-ph"]')?.className ?? ''
    const isFilled = (button: HTMLElement) => /-fill\b/.test(icon(button))
    for (const button of toggles())
      expect(isFilled(button), `${button.dataset.panel} on`).toBe(true)
    const wind = toggles().find(button => button.dataset.panel === 'wind')!
    wind.click()
    await nextTick()
    expect(wind.getAttribute('aria-pressed')).toBe('false')
    expect(isFilled(wind), 'wind off').toBe(false)
    expect(icon(wind)).toMatch(/i-ph[:-]wind(?!-fill)/)
    // the others stay on, and filled
    expect(toggles().filter(button => button !== wind).every(isFilled)).toBe(true)
    wind.click()
    await nextTick()
    expect(isFilled(wind), 'wind on again').toBe(true)
  })

  it('names each toggle by an aria-label that is its title, in the language of the page', async () => {
    wrapper = await mountSuspended(Meteogram, { props: { values, stationName: 'Berlin' }, attachTo: document.body })
    await flushPromises()
    expect(toggles()).toHaveLength(Object.keys(SERIES).length)
    const names = toggles().map(button => button.getAttribute('aria-label'))
    for (const button of toggles()) {
      expect(button.getAttribute('aria-label'), button.dataset.panel).toBeTruthy()
      expect(button.getAttribute('aria-label'), button.dataset.panel).toBe(button.getAttribute('title'))
    }
    expect(new Set(names).size).toBe(names.length)
    expect(names).toEqual(['Temperature', 'Wind', 'Precipitation', 'Cloud cover', 'Pressure'])
  })

  it('colours the icons of the summary line in the label colours, in the dark scheme the dark ones', async () => {
    wrapper = await mountSuspended(Meteogram, { props: { values, stationName: 'Berlin' }, attachTo: document.body })
    await flushPromises()
    const icons = () => [...document.body.querySelectorAll<HTMLElement>('[data-summary-icon]')]
    expect(icons().length).toBeGreaterThan(0)
    for (const icon of icons())
      expect(icon.getAttribute('style'), icon.dataset.summaryIcon).toBe(styled({ color: seriesLabelColor(SERIES[icon.dataset.summaryIcon as keyof typeof SERIES], false) }))
    document.documentElement.classList.add('dark')
    await flushPromises()
    for (const icon of icons())
      expect(icon.getAttribute('style'), `${icon.dataset.summaryIcon} at night`).toBe(styled({ color: seriesLabelColor(SERIES[icon.dataset.summaryIcon as keyof typeof SERIES], true) }))
    document.documentElement.classList.remove('dark')
  })

  it('draws the card of today with the edge tests/unit/button-contrast.test.ts holds to 3:1: blue-600 by day, blue-400 at night', async () => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-01T12:00:00Z') })
    wrapper = await mountSuspended(Meteogram, { props: { values, stationName: 'Berlin' }, attachTo: document.body })
    ;(wrapper.vm as unknown as { view: string }).view = 'compact'
    await vi.waitFor(() => expect(document.body.querySelector('.rounded-2xl')).not.toBeNull())
    const today = [...document.body.querySelectorAll('.rounded-2xl')].find(card => /today/i.test(card.textContent ?? ''))
    expect(today, 'the card of today').toBeDefined()
    expect(today!.classList.contains('border-blue-600')).toBe(true)
    expect(today!.classList.contains('dark:border-blue-400')).toBe(true)
  })
})

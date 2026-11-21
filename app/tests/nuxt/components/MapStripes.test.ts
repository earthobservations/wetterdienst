import type { H3Event } from 'h3'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData, useSettings } from '#imports'
import MapStripes from '~/components/MapStripes.vue'
import { STRIPE_PALETTES, stripeColour } from '~/utils/stripes'
import { stripesAnswer } from '../../helpers/stripes-answer'
import { ghcnAnnualAnswer, valuesAnswer } from '../../helpers/stripes-backend'

const en = JSON.parse(readFileSync(join(process.cwd(), 'i18n', 'locales', 'en.json'), 'utf8'))

// The climate stripes of the map's panel (GH-3650): the colours of the band, one stripe a year, and the sentence.

let years: number[] = []
let status = 200
// the station each request was for, whichever way it was asked
const asked: string[] = []
// the `unit_targets` each request carried, and the unit the backend answers in for them (GH-3980)
const unitTargetsAsked: unknown[] = []
// the whole query of each request, the address it went to, and how the days of a station of GHCN daily were made (`series.method`) in the answer
const queries: Array<Record<string, string>> = []
const urls: string[] = []
let method: 'midrange' | 'tavg' | null = null
/** The warnings of the answer of DWD's annual values: a station the lookup did not find, and a listing it went without */
let warnings: Array<{ code: string }> = []

/** The record of the years held: from 2000, in the unit asked for, as the backend converts them from degree Celsius */
function recordHeld(unitTargets: { temperature?: string }) {
  return years.map((value, index) => ({ year: 2000 + index, value: unitTargets.temperature === 'degree_fahrenheit' ? value * 1.8 + 32 : value }))
}
const unitSymbolOf = (unitTargets: { temperature?: string }) => ({ degree_fahrenheit: '°F', degree_kelvin: 'K' })[unitTargets.temperature as 'degree_kelvin'] ?? '°C'

/** A record of 12 years, which a scale needs at least 10 of: the values given, then years of 10 degrees */
const twelve = (...values: number[]) => [...values, ...Array.from<number>({ length: 12 - values.length }).fill(10)]

/** What the stripes are made of: the annual values of the API for a station of DWD, and of the app's own server for GHCN's (GH-4258) */
function serve(url: string, ghcn: boolean) {
  return (event: H3Event) => {
    const query = getQuery(event) as Record<string, string>
    urls.push(url)
    asked.push(String(ghcn ? query.station : query.stations))
    queries.push(query)
    const unitTargets = JSON.parse(String(query.unit_targets ?? '{}')) as { temperature?: string }
    unitTargetsAsked.push(unitTargets)
    if (status !== 200) {
      setResponseStatus(event, status)
      return { detail: 'This station has no complete years.' }
    }
    return ghcn
      ? ghcnAnnualAnswer(recordHeld(unitTargets), { unit: unitSymbolOf(unitTargets), method })
      : warnings.length
        ? { ...valuesAnswer([]), metadata: { warnings } }
        : valuesAnswer(recordHeld(unitTargets), { unit: unitSymbolOf(unitTargets) })
  }
}
registerEndpoint('/api/values', serve('/api/values', false))
registerEndpoint('/_ghcn/annual', serve('/_ghcn/annual', true))

const mounted: Array<{ unmount: () => void }> = []
async function mountStripes(stationId = '00011', ghcn = false) {
  const wrapper = await mountSuspended(MapStripes, { props: { stationId, stationName: 'Donaueschingen', ghcn }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
const colours = (wrapper: Awaited<ReturnType<typeof mountStripes>>) => wrapper.findAll('.map-stripes span').map(stripe => (stripe.element as HTMLElement).style.background)
const REFERENCE_SENTENCE = 'Colours: the mean of the whole record (2000–2011) is the centre of the scale, which spans ±2.6 standard deviations of the whole record (2000–2011) (Ed Hawkins\' method).'

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  useSettings().settings.value.units.temperature = 'degree_celsius'
  asked.length = 0
  unitTargetsAsked.length = 0
  queries.length = 0
  urls.length = 0
  method = null
  warnings = []
  status = 200
})

describe('the climate stripes of the panel', () => {
  it('colours a stripe for each year in the colour of the class the backend gives it, 16 colours from dark blue to dark red', async () => {
    // 20 years, rising evenly: 8.0 to 8.95
    years = Array.from({ length: 20 }, (_, index) => 8 + index * 0.05)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(20))
    const band = colours(wrapper)
    const classes = stripesAnswer(years.map((value, index) => ({ year: 2000 + index, value }))).values.map(item => item.stripe_class!)
    expect(band).toEqual(classes.map(stripeClass => stripeColour('temperature', stripeClass)))
    // the first year is the coldest class of the record, blue, and the last the warmest, red; each is not a colour of the one before
    expect(classes[0]).toBeLessThan(8)
    expect(classes[19]).toBeGreaterThan(8)
    expect(band.every(colour => STRIPE_PALETTES.temperature.includes(colour))).toBe(true)
    expect(new Set(band).size).toBeGreaterThan(8)
  })

  it('is as wide as the span, and says it in words: the years, the lowest and highest value, and what the colours are relative to', async () => {
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    const band = wrapper.find('[role="img"]')
    expect(band.attributes('aria-label')).toBe('Climate stripes of Donaueschingen')
    expect(band.attributes('aria-describedby')).toBe(wrapper.find('figcaption').attributes('id'))
    expect(wrapper.find('figcaption').text()).toBe(`From 2000 to 2011. Lowest value 8.0 °C in 2000, highest value 12.0 °C in 2001. ${REFERENCE_SENTENCE}`)
    // the classes of the whole record (the mean is 9.92, the standard deviation 0.89): 8 is 2.1 of it below (the class 1), 12 is 2.3 above (the 15th), 9 is 1.0 below (the 4th)
    const classes = stripesAnswer(years.map((value, index) => ({ year: 2000 + index, value }))).values.map(item => item.stripe_class!)
    expect(classes.slice(0, 3)).toEqual([1, 15, 4])
    expect(colours(wrapper)).toEqual(classes.map(stripeClass => stripeColour('temperature', stripeClass)))
  })

  it('is the lowest class of the red half, for years that are all alike, where there is no spread to class them by', async () => {
    years = Array.from<number>({ length: 12 }).fill(9)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(new Set(colours(wrapper))).toEqual(new Set([stripeColour('temperature', 8)]))
  })

  // whose data the band is made of, from the terms of the answer it was made of, and what was done to it (GH-4255)
  it('credits the provider of the answer under the band, with its licence and the note directly under the credit line', async () => {
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    const credit = wrapper.find('[data-testid="map-stripes-credit"]')
    expect(credit.find('[data-testid="provider-credit-line"]').text()).toBe('Source: Deutscher Wetterdienst, Creative Commons Attribution 4.0 International')
    expect(credit.find('a').attributes('href')).toBe('https://creativecommons.org/licenses/by/4.0/')
    const note = credit.find('[data-testid="processing-note"]')
    expect(note.text()).toBe(en.processingNote.base)
    expect(note.element.previousElementSibling).toBe(credit.find('[data-testid="provider-credit-line"]').element)
  })

  it('credits NOAA, as its own answer states it, for a station of GHCN daily', async () => {
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes('GM000010147', true)
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    const credit = wrapper.find('[data-testid="map-stripes-credit"]')
    expect(credit.find('[data-testid="provider-credit-line"]').text()).toContain('NOAA National Centers for Environmental Information (NCEI)')
    expect(credit.find('a').attributes('href')).toBe('https://creativecommons.org/publicdomain/zero/1.0/')
  })

  it('says why there are none, in the answer\'s words, and asks again on Retry', async () => {
    status = 422
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.find('[role="alert"]').text()).toContain('This station has no complete years.')
    status = 200
    years = twelve(8, 9)
    await wrapper.find('button').trigger('click')
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(asked).toEqual(['00011', '00011'])
  })

  it('asks for the unit of the settings, degree Celsius by default, and says the unit it is answered in', async () => {
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(unitTargetsAsked).toEqual([{ temperature: 'degree_celsius' }])
    expect(wrapper.find('figcaption').text()).toBe(`From 2000 to 2011. Lowest value 8.0 °C in 2000, highest value 12.0 °C in 2001. ${REFERENCE_SENTENCE}`)
  })

  it('asks for degree Fahrenheit where the settings choose it, writes the numbers in it, and colours them as before', async () => {
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(unitTargetsAsked).toEqual([{ temperature: 'degree_fahrenheit' }])
    expect(wrapper.find('figcaption').text()).toBe(`From 2000 to 2011. Lowest value 46.4 °F in 2000, highest value 53.6 °F in 2001. ${REFERENCE_SENTENCE}`)
    // the colours are relative: the same as in degree Celsius
    const classes = stripesAnswer(years.map((value, index) => ({ year: 2000 + index, value }))).values.map(item => item.stripe_class!)
    expect(colours(wrapper)).toEqual(classes.map(stripeClass => stripeColour('temperature', stripeClass)))
  })

  it('asks again, in the new unit, where the settings change while the stripes are shown', async () => {
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    useSettings().settings.value.units.temperature = 'degree_kelvin'
    await vi.waitFor(() => expect(unitTargetsAsked).toEqual([{ temperature: 'degree_celsius' }, { temperature: 'degree_kelvin' }]))
    await vi.waitFor(() => expect(wrapper.find('figcaption').text()).toContain('K in 2000'))
  })
})

describe('the climate stripes of a station of GHCN daily (GH-4078)', () => {
  it('asks the app\'s own server for a station of GHCN daily, and the API\'s annual values for a station of DWD, and no stripes route of the backend', async () => {
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes('GM000010147', true)
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(urls).toEqual(['/_ghcn/annual'])
    expect(queries[0]).toMatchObject({ kind: 'temperature', station: 'GM000010147' })
    wrapper.unmount()
    clearNuxtData()
    const dwd = await mountStripes('00011')
    await vi.waitFor(() => expect(dwd.findAll('.map-stripes span')).toHaveLength(12))
    expect(urls).toEqual(['/_ghcn/annual', '/api/values'])
    expect(queries[1]).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'annual/climate_summary/temperature_air_mean_2m', periods: 'historical', stations: '00011' })
    expect(queries[1]).not.toHaveProperty('kind')
    expect(urls.filter(url => url.includes('stripes'))).toEqual([])
  })

  it('says under the stripes how a day of the temperature was made: the midrange of the daily maximum and minimum, no 24-hour mean', async () => {
    years = twelve(8, 12, 9)
    method = 'midrange'
    const wrapper = await mountStripes('GM000010147', true)
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(wrapper.find('[data-testid="map-stripes-method"]').text()).toBe(en.stripes.methodMidrange)
    expect(wrapper.find('[data-testid="map-stripes-method"]').text()).toContain('not a 24-hour mean')
  })

  it('says the station\'s own daily mean was used, where it has no maximum and minimum', async () => {
    years = twelve(8, 12, 9)
    method = 'tavg'
    const wrapper = await mountStripes('GM000010147', true)
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(wrapper.find('[data-testid="map-stripes-method"]').text()).toBe(en.stripes.methodTavg)
  })

  it('says nothing of a method for a station of DWD', async () => {
    years = twelve(8, 12, 9)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(12))
    expect(wrapper.find('[data-testid="map-stripes-method"]').exists()).toBe(false)
  })

  it('says there are none, raises `none` and offers no retry where the backend refuses the station (400, 404, 422)', async () => {
    for (const refusal of [400, 404, 422]) {
      status = refusal
      const wrapper = await mountStripes('GBX', true)
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-stripes-refused"]').exists()).toBe(true))
      expect(wrapper.find('[data-testid="map-stripes-refused"]').text()).toBe('No climate stripes for this station.')
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
      expect(wrapper.find('button').exists()).toBe(false)
      expect(wrapper.emitted('none')).toHaveLength(1)
      wrapper.unmount()
      clearNuxtData()
    }
  })

  it('tells a failure that is no refusal (a 502, a 429) as a failure, with its retry, and a station of DWD\'s 422 as one as well', async () => {
    for (const [failure, ghcn] of [[502, true], [429, true], [422, false]] as const) {
      status = failure
      const wrapper = await mountStripes('GBX', ghcn)
      await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
      expect(wrapper.find('button').exists()).toBe(true)
      expect(wrapper.emitted('none')).toBeUndefined()
      wrapper.unmount()
      clearNuxtData()
    }
  })

  it('tells a station the lookup did not find, with a listing of DWD\'s gone, as a failure with its retry, and a station that is not there as no stripes', async () => {
    warnings = [{ code: 'file-skipped' }, { code: 'unknown-station' }]
    const wrapper = await mountStripes('00011')
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.find('[role="alert"]').text()).toContain('Try again later.')
    expect(wrapper.find('button').exists()).toBe(true)
    expect(wrapper.emitted('none')).toBeUndefined()
    wrapper.unmount()
    clearNuxtData()
    // no listing was left out: the station is not there, which for DWD's, listed by having stripes, is a failure as well, but of a 404
    warnings = [{ code: 'unknown-station' }]
    const absent = await mountStripes('00011')
    await vi.waitFor(() => expect(absent.find('[role="alert"]').exists()).toBe(true))
    expect(absent.find('[role="alert"]').text()).toContain('No station with a station_id similar to \'00011\' found')
  })
})

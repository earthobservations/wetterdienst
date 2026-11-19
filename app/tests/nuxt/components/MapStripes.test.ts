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

const en = JSON.parse(readFileSync(join(process.cwd(), 'i18n', 'locales', 'en.json'), 'utf8'))

// The climate stripes of the map's panel (GH-3650): the colours of the band, one stripe a year, and the sentence.

let years: number[] = []
let status = 200
const asked: string[] = []
// the `unit_targets` each request carried, and the unit the backend answers in for them (GH-3980)
const unitTargetsAsked: unknown[] = []
// the whole query of each request, and how the days of a station of GHCN daily were made (`series.method`) in the answer
const queries: Array<Record<string, string>> = []
let method: 'midrange' | 'tavg' | null = null
registerEndpoint('/api/stripes/values', (event) => {
  asked.push(String(getQuery(event).station))
  queries.push(getQuery(event) as Record<string, string>)
  const unitTargets = JSON.parse(String(getQuery(event).unit_targets ?? '{}')) as { temperature?: string }
  unitTargetsAsked.push(unitTargets)
  if (status !== 200) {
    setResponseStatus(event, status)
    return { detail: 'This station has no complete years.' }
  }
  return {
    metadata: {},
    series: { station: { station_id: '00011' }, resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', unit: unitTargets.temperature ?? 'degree_celsius', method },
    // the numbers in the unit asked for, as the backend converts them from degree Celsius, with the classes it gives them
    // against the whole record (a record this short has no year of 1971 to 2000 to class them by: the whole of it is the reference)
    ...stripesAnswer(years.map((value, index) => ({ year: 2000 + index, value: unitTargets.temperature === 'degree_fahrenheit' ? value * 1.8 + 32 : value }))),
  }
})

const mounted: Array<{ unmount: () => void }> = []
async function mountStripes(stationId = '00011', ghcn = false) {
  const wrapper = await mountSuspended(MapStripes, { props: { stationId, stationName: 'Donaueschingen', ghcn }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
const colours = (wrapper: Awaited<ReturnType<typeof mountStripes>>) => wrapper.findAll('.map-stripes span').map(stripe => (stripe.element as HTMLElement).style.background)
const REFERENCE_SENTENCE = 'Colours: the mean of the whole record (2000–2002) is the centre of the scale, which spans ±2.6 standard deviations of the whole record (2000–2002) (Ed Hawkins\' method).'

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  useSettings().settings.value.units.temperature = 'degree_celsius'
  asked.length = 0
  unitTargetsAsked.length = 0
  queries.length = 0
  method = null
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
    years = [8, 12, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    const band = wrapper.find('[role="img"]')
    expect(band.attributes('aria-label')).toBe('Climate stripes of Donaueschingen')
    expect(band.attributes('aria-describedby')).toBe(wrapper.find('figcaption').attributes('id'))
    expect(wrapper.find('figcaption').text()).toBe(`From 2000 to 2002. Lowest value 8.0 °C in 2000, highest value 12.0 °C in 2001. ${REFERENCE_SENTENCE}`)
    // the mean is 9.67 and the standard deviation 2.08: 8 is 0.8 of it below (the class 5), 12 is 1.1 above (the 11th), and 9 is 0.3 below (the 7th)
    expect(colours(wrapper)).toEqual([5, 11, 7].map(stripeClass => stripeColour('temperature', stripeClass)))
  })

  it('is the lowest class of the red half, for years that are all alike, where there is no spread to class them by', async () => {
    years = [9, 9, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    expect(new Set(colours(wrapper))).toEqual(new Set([stripeColour('temperature', 8)]))
  })

  it('says why there are none, in the answer\'s words, and asks again on Retry', async () => {
    status = 422
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.find('[role="alert"]').text()).toContain('This station has no complete years.')
    status = 200
    years = [8, 9]
    await wrapper.find('button').trigger('click')
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(2))
    expect(asked).toEqual(['00011', '00011'])
  })

  it('asks for the unit of the settings, degree Celsius by default, and says the unit it is answered in', async () => {
    years = [8, 12, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    expect(unitTargetsAsked).toEqual([{ temperature: 'degree_celsius' }])
    expect(wrapper.find('figcaption').text()).toBe(`From 2000 to 2002. Lowest value 8.0 °C in 2000, highest value 12.0 °C in 2001. ${REFERENCE_SENTENCE}`)
  })

  it('asks for degree Fahrenheit where the settings choose it, writes the numbers in it, and colours them as before', async () => {
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    years = [8, 12, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    expect(unitTargetsAsked).toEqual([{ temperature: 'degree_fahrenheit' }])
    expect(wrapper.find('figcaption').text()).toBe(`From 2000 to 2002. Lowest value 46.4 °F in 2000, highest value 53.6 °F in 2001. ${REFERENCE_SENTENCE}`)
    // the colours are relative: the same as in degree Celsius
    expect(colours(wrapper)).toEqual([5, 11, 7].map(stripeClass => stripeColour('temperature', stripeClass)))
  })

  it('asks again, in the new unit, where the settings change while the stripes are shown', async () => {
    years = [8, 12, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    useSettings().settings.value.units.temperature = 'degree_kelvin'
    await vi.waitFor(() => expect(unitTargetsAsked).toEqual([{ temperature: 'degree_celsius' }, { temperature: 'degree_kelvin' }]))
    await vi.waitFor(() => expect(wrapper.find('figcaption').text()).toContain('K in 2000'))
  })
})

describe('the climate stripes of a station of GHCN daily (GH-4078)', () => {
  it('asks with the provider and network of the layer, and with none for a station of DWD', async () => {
    years = [8, 12, 9]
    const wrapper = await mountStripes('GM000010147', true)
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    expect(queries[0]).toMatchObject({ kind: 'temperature', provider: 'noaa', network: 'ghcn', station: 'GM000010147' })
    wrapper.unmount()
    clearNuxtData()
    const dwd = await mountStripes('00011')
    await vi.waitFor(() => expect(dwd.findAll('.map-stripes span')).toHaveLength(3))
    expect(queries[1]).not.toHaveProperty('provider')
    expect(queries[1]).not.toHaveProperty('network')
  })

  it('says under the stripes how a day of the temperature was made: the midrange of the daily maximum and minimum, no 24-hour mean', async () => {
    years = [8, 12, 9]
    method = 'midrange'
    const wrapper = await mountStripes('GM000010147', true)
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    expect(wrapper.find('[data-testid="map-stripes-method"]').text()).toBe(en.stripes.methodMidrange)
    expect(wrapper.find('[data-testid="map-stripes-method"]').text()).toContain('not a 24-hour mean')
  })

  it('says the station\'s own daily mean was used, where it has no maximum and minimum', async () => {
    years = [8, 12, 9]
    method = 'tavg'
    const wrapper = await mountStripes('GM000010147', true)
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    expect(wrapper.find('[data-testid="map-stripes-method"]').text()).toBe(en.stripes.methodTavg)
  })

  it('says nothing of a method for a station of DWD', async () => {
    years = [8, 12, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
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
})

import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#imports'
import MapStripes from '~/components/MapStripes.vue'

// The climate stripes of the map's panel (GH-3650): the colours of the band, one stripe a year, and the sentence.

let years: number[] = []
let status = 200
const asked: string[] = []
registerEndpoint('/api/stripes/values', (event) => {
  asked.push(String(getQuery(event).station))
  if (status !== 200) {
    setResponseStatus(event, status)
    return { detail: 'This station has no complete years.' }
  }
  return {
    metadata: {},
    series: { station: { station_id: '00011' }, resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', unit: 'degree_celsius' },
    values: years.map((value, index) => ({ timestamp: `${2000 + index}-01-01T00:00:00+00:00`, value })),
  }
})

const mounted: Array<{ unmount: () => void }> = []
async function mountStripes(stationId = '00011') {
  const wrapper = await mountSuspended(MapStripes, { props: { stationId, stationName: 'Donaueschingen' }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
const colours = (wrapper: Awaited<ReturnType<typeof mountStripes>>) => wrapper.findAll('.map-stripes span').map(stripe => (stripe.element as HTMLElement).style.background)

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  asked.length = 0
  status = 200
})

describe('the climate stripes of the panel', () => {
  it('colours a stripe for each year from the coolest year, blue, to the warmest, red, by its place between them', async () => {
    // 20 years, rising evenly: 8.0 to 8.95
    years = Array.from({ length: 20 }, (_, index) => 8 + index * 0.05)
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(20))
    const band = colours(wrapper)
    // the stripes page's scale: the coolest year is its first stop (dark blue), the warmest its last (dark red)
    expect(band[0]).toBe('rgb(5, 48, 97)')
    expect(band[19]).toBe('rgb(178, 24, 43)')
    // year 10 of 20 is at 9/19 of the range: between the stops at 0.4 and 0.5, as Plotly mixes them
    expect(band[9]).toBe('rgb(220, 234, 240)')
    // each stripe is a different colour from the one before, as the years rise
    expect(new Set(band).size).toBe(20)
  })

  it('is as wide as the span, and says it in words: the years and the lowest and highest value', async () => {
    years = [8, 12, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    const band = wrapper.find('[role="img"]')
    expect(band.attributes('aria-label')).toBe('Climate stripes of Donaueschingen')
    expect(band.attributes('aria-describedby')).toBe(wrapper.find('figcaption').attributes('id'))
    expect(wrapper.find('figcaption').text()).toBe('From 2000 to 2002. Lowest value 8.0 °C in 2000, highest value 12.0 °C in 2001.')
    // 9 is a quarter of the way from 8 to 12: a quarter of the way between the stops at 0.2 and 0.4, (33, 102, 172) and (146, 197, 222)
    expect(colours(wrapper)).toEqual(['rgb(5, 48, 97)', 'rgb(178, 24, 43)', 'rgb(61, 126, 185)'])
  })

  it('is the middle of the scale, white, for years that are all alike, where there is no range to put them on', async () => {
    years = [9, 9, 9]
    const wrapper = await mountStripes()
    await vi.waitFor(() => expect(wrapper.findAll('.map-stripes span')).toHaveLength(3))
    expect(new Set(colours(wrapper))).toEqual(new Set(['rgb(247, 247, 247)']))
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
})

import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import AskTheWeather from '~/components/AskTheWeather.vue'
import { DEFAULT_PLACE, PLACE_STORAGE_KEY, townPlace } from '~/composables/usePlace'
import { dayValues, rainValues, summerValues } from '../../e2e/accessibility/ask-backend'
import { providersAnswer } from '../fixtures/providers'

// Ask the weather about a town found by its name (GH-3791): the town is the place of the questions, the measurements are read at the station nearest to it,
// and the answers say which and how far. Where no station is within 50 km nothing is asked of one: the answer says so and names the nearest. The place comes
// from a link here (`?lat=&lon=&placeName=`), which is what a shared link and the dialog's choice both write; the dialog's own choice is the palette test's
// and the end-to-end spec's. The backend is the accessibility spec's answers.

const requests: Array<{ path: string, query: URLSearchParams }> = []
function record(event: { path: string }, path: string) {
  const query = new URL(event.path, 'http://localhost').searchParams
  requests.push({ path, query })
  return query
}
const asked = (path: string) => requests.filter(request => request.path === path)

/** The station nearest to the town, as the test wants it: near (Andechs-Rothenfeld, 37 km from Bad Tölz) or far (Donaueschingen, over 200 km) */
const ANDECHS = { station_id: '00125', name: 'Andechs-Rothenfeld', region: 'Bayern', latitude: 47.9794, longitude: 11.1888, elevation: 680, start_timestamp: null, end_timestamp: null }
const DONAUESCHINGEN = { station_id: '00011', name: 'Donaueschingen (Landeplatz)', region: 'Baden-Württemberg', latitude: 47.9737, longitude: 8.5205, elevation: 680, start_timestamp: null, end_timestamp: null }
let nearestObservation = ANDECHS
/** The forecast point nearest: with the distance the backend gives it */
let forecastPoint = { station_id: 'M0814', name: 'BAD TOELZ', region: null, latitude: 47.77, longitude: 11.55, elevation: 668, start_timestamp: null, end_timestamp: null, distance: 1.2 }

registerEndpoint('/api/stations', (event) => {
  const query = record(event, 'stations')
  if (query.get('network') === 'mosmix')
    return { stations: [forecastPoint] }
  return { stations: [nearestObservation] }
})
registerEndpoint('/api/providers', () => providersAnswer())
registerEndpoint('/api/values', (event) => {
  const query = record(event, 'values')
  const station = query.get('stations') ?? ''
  if (query.get('network') === 'mosmix')
    return { values: rainValues(station) }
  const parameters = query.get('parameters') ?? ''
  return { values: parameters.startsWith('monthly/') ? summerValues(station) : dayValues(station, query.get('timestamp')) }
})

const TOWN = '/?lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany'

const mounted: Array<{ unmount: () => void }> = []
async function mountAsk(route: string) {
  const wrapper = await mountSuspended(AskTheWeather, { attachTo: document.body, route })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  nearestObservation = ANDECHS
  forecastPoint = { station_id: 'M0814', name: 'BAD TOELZ', region: null, latitude: 47.77, longitude: 11.55, elevation: 668, start_timestamp: null, end_timestamp: null, distance: 1.2 }
  usePlace().place.value = DEFAULT_PLACE
  localStorage.removeItem(PLACE_STORAGE_KEY)
})
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  requests.length = 0
})

describe('the town of a link', () => {
  it('becomes the place of the questions, with where it lies, and the station nearest to it is looked up once, by the town\'s position', async () => {
    const wrapper = await mountAsk(`${TOWN}&ask=season`)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Bad Tölz'))
    expect(wrapper.find('[data-testid="place-region"]').text()).toBe('Bayern, Germany')
    const nearest = asked('stations').find(request => request.query.get('network') === 'observation')!
    expect(Object.fromEntries(nearest.query)).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary', latitude: '47.761', longitude: '11.5596', rank: '1' })
    expect(usePlace().place.value).toMatchObject({
      name: 'Bad Tölz',
      region: 'Bayern, Germany',
      id: '00125',
      latitude: 47.761,
      longitude: 11.5596,
      town: { station: { id: '00125', name: 'Andechs-Rothenfeld' } },
    })
    expect(wrapper.find('[data-testid="question-season"]').text()).toContain('than usual here?')
    expect(wrapper.find('[data-testid="question-rain"]').text()).toContain('Will it rain in Bad Tölz tomorrow?')
  })

  it('has the answer read at the station nearest to it, and says which and how far it is from the town', async () => {
    const wrapper = await mountAsk(`${TOWN}&ask=season`)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="answer-verdict"]').exists()).toBe(true))
    // the measurements are the station's, not a station by the town's name
    expect(asked('values')[0]!.query.get('stations')).toBe('00125')
    const line = wrapper.find('[data-testid="answer-station"]').text()
    expect(line).toMatch(/^Read at Andechs-Rothenfeld \(00125\), the weather station nearest to Bad Tölz, \d+ km away\.$/)
    // 37 km, about: the distance is the great circle between the town's point and the station's
    expect(line).toContain('37 km')
    expect(wrapper.find('[data-testid="answer-far"]').exists()).toBe(false)
  })

  it('says there is no weather station near where the nearest is over 50 km away, names it, asks for no readings and gives no answer', async () => {
    nearestObservation = DONAUESCHINGEN
    const wrapper = await mountAsk(`${TOWN}&ask=season`)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="answer-far"]').exists()).toBe(true))
    const far = wrapper.find('[data-testid="answer-far"]').text()
    expect(far).toContain('There is no weather station within 50 km of Bad Tölz.')
    expect(far).toContain('The nearest, Donaueschingen (Landeplatz) (00011), is 2')
    expect(far).toContain('so no answer is given.')
    expect(wrapper.find('[data-testid="answer-verdict"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="answer-station"]').exists()).toBe(false)
    // no link into the data of a station that is another place's
    expect(wrapper.find('[data-testid="answer-actions"]').exists()).toBe(false)
    expect(asked('values')).toEqual([])
    // a polite status, so that a screen reader says it
    expect(wrapper.find('[data-testid="answer-status"]').text()).toContain('There is no weather station within 50 km of Bad Tölz.')
  })

  it('says the same of the forecast where its nearest point is over 50 km away, and fetches no forecast', async () => {
    forecastPoint = { ...forecastPoint, name: 'MUENCHEN-STADT', station_id: '10865', distance: 120.4 }
    const wrapper = await mountAsk(`${TOWN}&ask=rain`)
    await vi.waitFor(() => expect(wrapper.text()).toContain('There is no forecast point within 50 km of Bad Tölz.'))
    expect(wrapper.text()).toContain('The nearest, MUENCHEN-STADT, is 120 km away')
    expect(wrapper.find('[data-testid="answer-verdict"]').exists()).toBe(false)
    expect(asked('values')).toEqual([])
  })

  it('names the forecast point and its distance from the town where it is near', async () => {
    const wrapper = await mountAsk(`${TOWN}&ask=rain`)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="answer-verdict"]').exists()).toBe(true))
    expect(wrapper.text()).toContain('Forecast for BAD TOELZ, the forecast point nearest to Bad Tölz (1.2 km away).')
    expect(asked('values')[0]!.query.get('stations')).toBe('M0814')
  })

  it('is not looked up again where the town is the place already, and is kept in the browser with its station', async () => {
    const wrapper = await mountAsk(TOWN)
    await vi.waitFor(() => expect(usePlace().place.value.town).toBeDefined())
    // another key of the link changes: the town is the same
    await navigateTo('/?ask=rain&lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany')
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(asked('stations').filter(request => request.query.get('network') === 'observation')).toHaveLength(1)
    const kept = JSON.parse(localStorage.getItem(PLACE_STORAGE_KEY)!)
    expect(kept).toMatchObject({ id: '00125', name: 'Bad Tölz', town: { station: { id: '00125', name: 'Andechs-Rothenfeld' } } })
    expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Bad Tölz')
  })

  it('is no town where the link has a position and no name (what the map writes), or no position', async () => {
    const wrapper = await mountAsk('/?lat=47.7610&lon=11.5596')
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(usePlace().place.value).toEqual(DEFAULT_PLACE)
    expect(asked('stations')).toEqual([])
    wrapper.unmount()
    const named = await mountAsk('/?placeName=Bad%20T%C3%B6lz')
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(usePlace().place.value).toEqual(DEFAULT_PLACE)
    expect(named.find('[data-testid="place-region"]').exists()).toBe(false)
  })

  it('says so where no station could be found for it', async () => {
    nearestObservation = undefined as never
    const wrapper = await mountAsk(TOWN)
    await vi.waitFor(() => expect(wrapper.text()).toContain('No weather station could be found for this place.'))
    expect(usePlace().place.value).toEqual(DEFAULT_PLACE)
  })
})

describe('a town as a place', () => {
  const town = { name: 'Bad Tölz', region: 'Bayern, Germany', latitude: 47.761, longitude: 11.5596 }

  it('names the nearest station and how far it is, from the great circle between the two', () => {
    const place = townPlace(town, ANDECHS)!
    expect(place).toMatchObject({ id: '00125', name: 'Bad Tölz', region: 'Bayern, Germany' })
    expect(place.town!.station.distanceKm).toBeCloseTo(36.8, 0)
    expect(place.town!.station.name).toBe('Andechs-Rothenfeld')
  })

  it('is none where there is no station, or the station has no position', () => {
    expect(townPlace(town, undefined)).toBeNull()
    expect(townPlace(town, { ...ANDECHS, latitude: null as never })).toBeNull()
  })
})

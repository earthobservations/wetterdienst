import type { VueWrapper } from '@vue/test-utils'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MeteogramPage from '~/pages/meteogram.vue'

// The Forecast with a place found by its name (GH-3791), in a file of its own as the other pages' tests leave their pages mounted. A link with a place and a
// station (and the run and the display of the chart) must keep all of them whichever of the two lookups it waits for: the page must not write the address
// while the link's station is still being looked up, or the station, the run and the display are lost.

const STATIONS: Record<string, { station_id: string, name: string, latitude: number, longitude: number, elevation: number }> = {
  M0814: { station_id: 'M0814', name: 'BAD TOELZ', latitude: 47.77, longitude: 11.55, elevation: 668 },
  M0818: { station_id: 'M0818', name: 'TEGERNSEE', latitude: 47.71, longitude: 11.76, elevation: 735 },
  M0816: { station_id: 'M0816', name: 'KOCHEL AM SEE', latitude: 47.65, longitude: 11.37, elevation: 614 },
}
const LINK = 'lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany'
const ISSUE = '2026-10-03T06:00:00'

describe('the forecast page with a place', () => {
  let wrapper: VueWrapper | undefined
  const endpoints: Array<() => void> = []
  /** What the stations request was given, one entry for each: the one by id (the link's station) and the one by position (the stations near the place) */
  const requests: Array<Record<string, unknown>> = []
  let holdStation: Promise<void> | undefined
  let holdNear: Promise<void> | undefined
  let failStation = false

  beforeEach(() => {
    requests.length = 0
    holdStation = undefined
    holdNear = undefined
    failStation = false
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    endpoints.push(registerEndpoint('/api/stations', async (event) => {
      const query = getQuery(event)
      requests.push(query)
      if (query.latitude) {
        if (holdNear)
          await holdNear
        return { stations: [STATIONS.M0814, STATIONS.M0818, STATIONS.M0816] }
      }
      if (holdStation)
        await holdStation
      if (failStation)
        throw createError({ statusCode: 503, statusMessage: 'busy' })
      const station = STATIONS[String(query.stations)]
      return { stations: station ? [station] : [] }
    }))
    endpoints.push(registerEndpoint('/api/issues', () => ({ issues: [] })))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
  })

  const vm = () => wrapper!.vm as any
  const held = () => {
    let release: () => void = () => {}
    const promise = new Promise<void>((resolve) => {
      release = resolve
    })
    return { promise, release }
  }

  it('keeps the station, the run and the display of a link that names a place too, whichever lookup comes last', async () => {
    const { promise, release } = held()
    holdStation = promise
    wrapper = await mountSuspended(MeteogramPage, { route: `/meteogram?station=M0818&issue=${ISSUE}&horizon=3d&panels=temperature&view=chart&${LINK}` })
    // the place is shown at once and the stations near it are there; the link's station is still being looked up
    await vi.waitFor(() => expect(vm().stationsNearPlace.length).toBe(3))
    await new Promise(resolve => setTimeout(resolve, 100))
    // the address was not written meanwhile
    expect(useRoute().query).toMatchObject({ station: 'M0818', issue: ISSUE, horizon: '3d', panels: 'temperature', view: 'chart', placeName: 'Bad Tölz' })
    release()
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0818'))
    // the station of the link, not the closest of the place, and its run
    expect(vm().selectedIssue).toBe(ISSUE)
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(useRoute().query).toMatchObject({ station: 'M0818', issue: ISSUE, horizon: '3d', panels: 'temperature', view: 'chart', lat: '47.7610', lon: '11.5596', placeName: 'Bad Tölz', placeRegion: 'Bayern, Germany' })
    expect(vm().place).toMatchObject({ name: 'Bad Tölz' })
  })

  it('keeps them where the stations near the place are the lookup that comes last', async () => {
    const { promise, release } = held()
    holdNear = promise
    wrapper = await mountSuspended(MeteogramPage, { route: `/meteogram?station=M0818&issue=${ISSUE}&horizon=3d&${LINK}` })
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0818'))
    expect(vm().selectedIssue).toBe(ISSUE)
    // the place's stations are still on their way: the page shows the place and says it is looking
    expect(vm().nearState).toBe('loading')
    expect(useRoute().query).toMatchObject({ station: 'M0818', issue: ISSUE, horizon: '3d', placeName: 'Bad Tölz' })
    release()
    await vi.waitFor(() => expect(vm().nearState).toBe('ready'))
    // the closest station is not picked over the link's
    expect(vm().selectedStation?.station_id).toBe('M0818')
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(useRoute().query).toMatchObject({ station: 'M0818', issue: ISSUE, horizon: '3d' })
  })

  it('shows the station the header search names from a place view, when its lookup is slow: the place goes at once and the old station is not written back', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: `/meteogram?${LINK}` })
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0814'))
    await vi.waitFor(() => expect(useRoute().query.station).toBe('M0814'))
    const { promise, release } = held()
    holdStation = promise
    // Ctrl/⌘ K, a station: the link has no place
    await navigateTo('/meteogram?station=M0816')
    await vi.waitFor(() => expect(requests.filter(query => query.stations === 'M0816')).toHaveLength(1))
    // the place is gone, and the address was not rewritten with the station that was shown
    await vi.waitFor(() => expect(vm().place).toBeNull())
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(useRoute().query.station).toBe('M0816')
    release()
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0816'))
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(useRoute().query.station).toBe('M0816')
    expect(useRoute().query.placeName).toBeUndefined()
  })

  it('shows the place\'s closest station, and says the link\'s station was not found, where the station of a link with a place is unknown', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: `/meteogram?station=XXXX&${LINK}` })
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0814'))
    expect(vm().stationMissing).toBe('XXXX')
    await vi.waitFor(() => expect(useRoute().query.station).toBe('M0814'))
    expect(useRoute().query.placeName).toBe('Bad Tölz')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="place-station-missing"]').text()).toBe('The station XXXX named in the link was not found.'))
  })

  it('does the same where the lookup of the link\'s station fails', async () => {
    failStation = true
    wrapper = await mountSuspended(MeteogramPage, { route: `/meteogram?station=M0818&${LINK}` })
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0814'))
    expect(vm().stationMissing).toBe('M0818')
  })

  it('has nothing to fall back to where a link names an unknown station and no place, as it did', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=XXXX' })
    await new Promise(resolve => setTimeout(resolve, 200))
    expect(vm().selectedStation).toBeNull()
    expect(vm().stationMissing).toBe('')
  })

  it('picks the closest station of a link that names a place and no station, and writes both to the address', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: `/meteogram?${LINK}` })
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0814'))
    await vi.waitFor(() => expect(useRoute().query).toMatchObject({ station: 'M0814', placeName: 'Bad Tölz', lat: '47.7610' }))
  })

  it('keeps a place with no station within reach in the address, and no station', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?lat=48.8566&lon=2.3522&placeName=Paris&placeRegion=France' })
    await vi.waitFor(() => expect(vm().nearState).toBe('ready'))
    expect(vm().selectedStation).toBeNull()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(useRoute().query).toMatchObject({ placeName: 'Paris', lat: '48.8566' })
    expect(useRoute().query.station).toBeUndefined()
  })

  it('asks for the stations near a place chosen in the search by the position to four decimals, whatever Photon gave', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram' })
    await vm().onPlace({ id: 'N1', name: 'Bad Tölz', kind: 'town', region: 'Bayern, Germany', latitude: 47.76143219, longitude: 11.55834567 })
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0814'))
    // the UV index and the pollen load ask for the nearest place and state by the station's position too, which are not the forecast's
    const byPosition = requests.filter(query => query.latitude && query.network === 'mosmix')
    expect(byPosition).toHaveLength(1)
    expect(byPosition[0]).toMatchObject({ latitude: '47.7614', longitude: '11.5583', rank: '5' })
    expect(vm().place).toMatchObject({ latitude: 47.7614, longitude: 11.5583 })
    await vi.waitFor(() => expect(useRoute().query).toMatchObject({ lat: '47.7614', lon: '11.5583', station: 'M0814' }))
  })

  it('takes the place away where the reader picks a station, and keeps it where one of its stations is shown instead', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: `/meteogram?${LINK}` })
    await vi.waitFor(() => expect(vm().selectedStation?.station_id).toBe('M0814'))
    vm().onPickNear(STATIONS.M0818)
    await vi.waitFor(() => expect(useRoute().query.station).toBe('M0818'))
    expect(useRoute().query.placeName).toBe('Bad Tölz')
    vm().onPick([STATIONS.M0816])
    await vi.waitFor(() => expect(useRoute().query.station).toBe('M0816'))
    await vi.waitFor(() => expect(useRoute().query.placeName).toBeUndefined())
    expect(vm().place).toBeNull()
  })
})

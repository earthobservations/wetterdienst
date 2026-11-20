import process from 'node:process'
import { expect, test } from '@playwright/test'

// The app's own list of the stations of NOAA GHCN daily (GH-4267, `server/routes/_ghcn/map-stations.get.ts`), through the running app to the
// real backend, which makes it from its list of 133k stations and the app's server keeps for a day. The first request may find the
// backend with a cold cache (NOAA's list is downloaded and parsed), so it is given more than the 90 s the route waits for it.
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7890'
// longer than the route waits for the backend (90 s), so that a backend that is too slow is the route's 502 and not this request's timeout
const SLOW = 120_000

test.describe('the list of the GHCN daily stations of the map', () => {
  test.setTimeout(SLOW + 60_000)

  test('is the backend\'s stations as columns, which are as long as the list says', async ({ request }) => {
    const response = await request.get('/_ghcn/map-stations', { timeout: SLOW })
    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toContain('application/json')
    const list = await response.json()
    expect(list.count).toBeGreaterThan(100_000)
    for (const column of ['station_id', 'latitude', 'longitude', 'first_year', 'last_year', 'name', 'wmo_id'])
      expect(list[column]).toHaveLength(list.count)
    // Central Park in New York City, a station that is there since 1869
    const at = list.station_id.indexOf('USW00094728')
    expect(at).toBeGreaterThan(-1)
    expect(list.first_year[at]).toBeLessThan(1900)
    expect(list.latitude[at]).toBeCloseTo(40.78, 1)

    // the same stations as the backend's own list, which is 44 MB of objects (the first ones are enough to know)
    const direct = await request.get(`${BACKEND_URL}/api/stations?provider=noaa&network=ghcn&parameters=daily/data&stations=USW00094728`, { timeout: SLOW })
    const station = (await direct.json()).stations[0]
    expect(station.station_id).toBe('USW00094728')
    expect(station.latitude).toBe(list.latitude[at])
    expect(station.longitude).toBe(list.longitude[at])
    expect(station.name).toBe(list.name[at])
  })

  test('is kept for a day: a second request is not a second one at the backend, and a conditional one is answered with no body', async ({ request }) => {
    const first = await request.get('/_ghcn/map-stations', { timeout: SLOW })
    const second = await request.get('/_ghcn/map-stations', { timeout: SLOW })
    // the backend says when it answered: a second answer of it would say another time
    expect((await second.json()).retrieved_at).toBe((await first.json()).retrieved_at)
    // the day that is left (the second that has gone since it was made is taken off) and the day it may be served stale
    expect(second.headers()['cache-control']).toMatch(/^public, s-maxage=\d+, stale-while-revalidate=86400$/)
    const etag = second.headers().etag
    expect(etag).toBeTruthy()
    const conditional = await request.get('/_ghcn/map-stations', { headers: { 'if-none-match': etag! }, timeout: SLOW })
    expect(conditional.status()).toBe(304)
    expect(await conditional.body()).toHaveLength(0)
  })
})

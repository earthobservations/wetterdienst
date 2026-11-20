import process from 'node:process'
import { expect, test } from '@playwright/test'

// The app's own list of the stations of NOAA GHCN daily (GH-4267, `server/api/map/ghcn-stations.get.ts`), through the running app to the
// real backend, which makes it from its list of 133k stations and the app's server keeps for a day. The first request may find the
// backend with a cold cache (NOAA's list is downloaded and parsed), so it is given the time the backend's own large answers are.
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7890'
const SLOW = 240_000

test.describe('the list of the GHCN daily stations of the map', () => {
  test.setTimeout(SLOW + 60_000)

  test('is the backend\'s stations as columns, which are as long as the list says', async ({ request }) => {
    const response = await request.get('/api/map/ghcn-stations', { timeout: SLOW })
    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toContain('application/json')
    const list = await response.json()
    expect(list.count).toBeGreaterThan(100_000)
    for (const column of ['station_id', 'latitude', 'longitude', 'first_year', 'last_year', 'name'])
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
    const first = await request.get('/api/map/ghcn-stations', { timeout: SLOW })
    const second = await request.get('/api/map/ghcn-stations', { timeout: SLOW })
    // the backend says when it answered: a second answer of it would say another time
    expect((await second.json()).retrieved_at).toBe((await first.json()).retrieved_at)
    expect(second.headers()['cache-control']).toContain('s-maxage=86400')
    const etag = second.headers().etag
    expect(etag).toBeTruthy()
    const conditional = await request.get('/api/map/ghcn-stations', { headers: { 'if-none-match': etag! }, timeout: SLOW })
    expect(conditional.status()).toBe(304)
    expect(await conditional.body()).toHaveLength(0)
  })
})

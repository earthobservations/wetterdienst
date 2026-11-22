import { expect, test } from '@playwright/test'

// The stations the search of the header finds by name (GH-3790, `server/routes/_search/stations.get.ts`), through the running app to the real
// backend: the app's server matches the two lists it keeps (DWD's measuring stations, NOAA GHCN daily; the forecast's points are the backend's) and answers the
// best few of each. The first request after a start may find the backend with a cold cache (NOAA's list of 133k stations is downloaded and
// parsed), so it is given more than the 5 s the route waits for a list: it then answers `pending` for it, which the search asks again after.
const SLOW = 120_000

interface Answer {
  query: string
  networks: Array<{ network: string, total: number, stations: Array<{ station_id: string, name: string | null, reporting: boolean }> }>
  pending: string[]
  failed: string[]
}

/** The answer once every list is there: a cold GHCN list is `pending` until the backend has made it */
async function searched(request: import('@playwright/test').APIRequestContext, query: string): Promise<Answer> {
  const deadline = Date.now() + SLOW
  for (;;) {
    const response = await request.get(`/_search/stations?q=${encodeURIComponent(query)}&limit=4&lists=measured,ghcn`, { timeout: SLOW })
    expect(response.status()).toBe(200)
    const answer = await response.json() as Answer
    if (!answer.pending.length || Date.now() > deadline)
      return answer
    await new Promise(resolve => setTimeout(resolve, 3000))
  }
}

test.describe('the stations of the search', () => {
  test.setTimeout(SLOW + 60_000)

  test('are the best few of each of the two lists of the server for a name, with how many there are in all, folded as the search folds', async ({ request }) => {
    const answer = await searched(request, 'HAMBURG')
    expect(answer.failed).toEqual([])
    expect(answer.pending).toEqual([])
    expect(answer.networks.map(found => found.network)).toEqual(['measured', 'ghcn'])
    for (const found of answer.networks) {
      expect(found.total).toBeGreaterThanOrEqual(1)
      expect(found.stations.length).toBeLessThanOrEqual(4)
    }
  })

  test('are found by a name in either spelling of an umlaut, and in any case and order of the words', async ({ request }) => {
    // DWD's measuring stations write `Fuhlsbüttel`, NOAA's list `FUHLSBUETTEL`
    for (const query of ['Fuhlsbüttel hamburg', 'FUHLSBUETTEL', 'hamburg fuhlsbuettel']) {
      const answer = await searched(request, query)
      const byNetwork = Object.fromEntries(answer.networks.map(found => [found.network, found]))
      expect(byNetwork.measured!.stations.map(station => station.station_id), query).toContain('01975')
      expect(byNetwork.ghcn!.stations.map(station => station.station_id), query).toContain('GM000010147')
    }
  })

  test('finds a station by its id or its WMO number, and nothing for fewer than three characters', async ({ request }) => {
    const byNumber = await searched(request, '10147')
    expect(byNumber.networks.find(found => found.network === 'measured')!.stations[0]!.station_id).toBe('01975')
    expect((await searched(request, 'ha')).networks).toEqual([])
  })

  test('answers an invalid query as a 422 problem, as the backend does, and counts nothing it was not asked for', async ({ request }) => {
    for (const query of ['', 'q=hamburg&limit=0', 'q=hamburg&limit=11', 'q=hamburg&lists=forecast', `q=${'x'.repeat(101)}`]) {
      const response = await request.get(`/_search/stations?${query}`)
      expect(response.status(), query).toBe(422)
      expect(response.headers()['content-type']).toContain('application/problem+json')
      expect((await response.json()).type).toBe('urn:wetterdienst:problem:invalid-parameters')
    }
  })

  test('is a few hundred bytes for a keystroke and, with its lists kept, answers in milliseconds', async ({ request }) => {
    await searched(request, 'hamburg')
    const started = Date.now()
    const response = await request.get('/_search/stations?q=berlin&limit=4&lists=measured,ghcn')
    const took = Date.now() - started
    expect((await response.body()).length).toBeLessThan(5000)
    expect(took).toBeLessThan(1000)
    expect(response.headers()['cache-control']).toBe('private, max-age=300')
  })
})

import type { Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import type { PlacesAnswer } from '../../shared/utils/places'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createPlacesSearch,
  parsePlacesQuery,
  PLACES_PER_SECOND,
  PLACES_PHOTON_BASE,
  PLACES_USER_AGENT,
  placesCacheKey,
  placesSearchHandler,
  placesSearchOn,
} from '../../server/utils/placesSearch'
import { PLACES_ATTRIBUTION } from '../../shared/utils/places'

// The places the search of the header finds by name (GH-3790, GH-3791): the route that asks Photon for them from the server, its cache, its pace
// towards Photon, its switch, and what it passes on to Photon, which is the text and nothing of the reader. Photon itself is never asked: every
// test hands the route a stand-in for `fetch`.

// The handler as Nitro runs it: h3's own functions are its auto-imports, and so are the utilities.
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

const feature = (lon: number, lat: number, properties: Record<string, unknown>) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties })
const BAD_TOELZ = feature(11.5583, 47.7614, { osm_id: 240109189, osm_type: 'N', osm_key: 'place', osm_value: 'town', type: 'city', name: 'Bad Tölz', state: 'Bayern', country: 'Deutschland' })
const photon = (...features: unknown[]) => new Response(JSON.stringify({ type: 'FeatureCollection', features }), { headers: { 'content-type': 'application/json;charset=UTF-8' } })

describe('what the route reads from a request', () => {
  it('takes a text of three characters or more with a letter, as one line, and the language of Photon\'s that the reader\'s locale has, else English', () => {
    expect(parsePlacesQuery({ q: '  bad   tölz ', lang: 'de' })).toEqual({ q: 'bad tölz', lang: 'de' })
    expect(parsePlacesQuery({ q: 'Paris', lang: 'fr-CH' })).toEqual({ q: 'Paris', lang: 'fr' })
    // Photon answers a language it does not have with a 400, so none is passed on
    expect(parsePlacesQuery({ q: 'Praha', lang: 'cs' })).toEqual({ q: 'Praha', lang: 'en' })
    expect(parsePlacesQuery({ q: 'Praha' })).toEqual({ q: 'Praha', lang: 'en' })
  })

  it('refuses what is no name of a place: nothing, two characters, no letter, too long, and a language that is no code', () => {
    const errorsOf = (query: Record<string, unknown>) => ('errors' in parsePlacesQuery(query) ? (parsePlacesQuery(query) as { errors: Array<{ loc: string[] }> }).errors.map(error => error.loc[1]) : [])
    expect(errorsOf({})).toEqual(['q'])
    expect(errorsOf({ q: 'ab' })).toEqual(['q'])
    expect(errorsOf({ q: '52.5200, 13.4' })).toEqual(['q'])
    expect(errorsOf({ q: 'x'.repeat(101) })).toEqual(['q'])
    expect(errorsOf({ q: ['a', 'b'] })).toEqual(['q'])
    expect(errorsOf({ q: 'Paris', lang: 'de; drop' })).toEqual(['lang'])
    expect(errorsOf({ q: 'Paris', lang: ['de'] })).toEqual(['lang'])
  })

  it('keeps the cache key of a text as one line in lower case, with the language: the same place asked for in another case or spacing is one entry', () => {
    expect(placesCacheKey('  Bad   TÖLZ', 'de')).toBe(placesCacheKey('bad tölz', 'de'))
    expect(placesCacheKey('bad tölz', 'de')).not.toBe(placesCacheKey('bad tölz', 'en'))
  })
})

describe('the switch of the operator', () => {
  it('is on by default and for the words that say on, and off for anything else, so that a typing mistake does not leave the search running', () => {
    for (const on of [undefined, null, '', 'on', 'ON', 'true', '1', 'yes', 'enabled', ' on '])
      expect(placesSearchOn(on), String(on)).toBe(true)
    for (const off of ['off', 'false', '0', 'no', 'disabled', 'of', 'nope'])
      expect(placesSearchOn(off), off).toBe(false)
  })
})

describe('the search of places', () => {
  /** A search with a clock the test moves, a wait that takes no time (and is counted), and a `fetch` that is asked what the route asks Photon */
  function searcher(answer: (url: URL, init: RequestInit) => Response | Promise<Response> = () => photon(BAD_TOELZ), extra: Parameters<typeof createPlacesSearch>[0] = {}) {
    const clock = { now: 1_000_000 }
    const asked: Array<{ url: URL, init: RequestInit }> = []
    const waits: number[] = []
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      asked.push({ url: new URL(url as URL), init: init! })
      return answer(new URL(url as URL), init!)
    })
    const search = createPlacesSearch({
      fetcher: fetcher as unknown as typeof fetch,
      now: () => clock.now,
      sleep: async (ms) => {
        waits.push(ms)
      },
      ...extra,
    })
    return { search, clock, asked, waits, fetcher }
  }

  it('asks Photon for the text, the language and a limit, with a User-Agent that names the project, and nothing of the reader', async () => {
    const { search, asked } = searcher()
    const places = await search.search('bad tölz', 'de')
    expect(places).toEqual([{ id: 'N240109189', name: 'Bad Tölz', kind: 'town', region: 'Bayern, Deutschland', latitude: 47.7614, longitude: 11.5583 }])
    expect(asked).toHaveLength(1)
    const { url, init } = asked[0]!
    expect(`${url.origin}${url.pathname}`).toBe(PLACES_PHOTON_BASE)
    expect([...url.searchParams.keys()].sort()).toEqual(['lang', 'limit', 'q'])
    expect(url.searchParams.get('q')).toBe('bad tölz')
    expect(url.searchParams.get('lang')).toBe('de')
    // the headers are the two the route sets, and no other: no cookie, no Referer, no Accept-Language, no X-Forwarded-For
    expect(init.headers).toEqual({ 'user-agent': PLACES_USER_AGENT, 'accept': 'application/json' })
    expect(PLACES_USER_AGENT).toContain('https://github.com/earthobservations/wetterdienst')
    expect(init.redirect).toBe('error')
  })

  it('serves a text asked for again from its cache, whatever its case or spacing, and asks again for another language, another text or after a day', async () => {
    const { search, asked, clock } = searcher()
    await search.search('bad tölz', 'de')
    await search.search('Bad   TÖLZ ', 'de')
    expect(asked).toHaveLength(1)
    await search.search('bad tölz', 'en')
    await search.search('bad tölzer', 'de')
    expect(asked).toHaveLength(3)
    clock.now += 24 * 3_600_000 - 1
    await search.search('bad tölz', 'de')
    expect(asked).toHaveLength(3)
    clock.now += 1
    await search.search('bad tölz', 'de')
    expect(asked).toHaveLength(4)
    expect(search.cacheSize).toBe(3)
  })

  it('asks Photon once for askers of the same text that come while it is asking', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const { search, asked } = searcher(async () => {
      await held
      return photon(BAD_TOELZ)
    })
    const answers = [search.search('bad tölz', 'de'), search.search('bad tölz', 'de'), search.search('BAD TÖLZ', 'de')]
    release()
    expect((await Promise.all(answers)).map(places => places.length)).toEqual([1, 1, 1])
    expect(asked).toHaveLength(1)
  })

  it('paces the requests to Photon for the whole app, and refuses the one that would wait too long, which it does not queue', async () => {
    const { search, asked, waits } = searcher(undefined, { maxWaitMs: 1100 })
    const interval = 1000 / PLACES_PER_SECOND
    // one at once, then one every third of a second: the fifth would wait 1.33 s, past the 1.1 s it may
    const results = await Promise.allSettled(['bad aaa', 'bad bbb', 'bad ccc', 'bad ddd', 'bad eee'].map(text => search.search(text, 'de')))
    expect(results.map(result => result.status)).toEqual(['fulfilled', 'fulfilled', 'fulfilled', 'fulfilled', 'rejected'])
    expect(waits.map(Math.round)).toEqual([0, 1, 2, 3].map(step => Math.round(step * interval)))
    expect(asked).toHaveLength(4)
    const refused = (results[4] as PromiseRejectedResult).reason
    expect(refused).toMatchObject({ status: 503, type: 'urn:wetterdienst:problem:places-busy', retryAfter: 1 })
  })

  it('answers a timeout as a 504, pauses Photon for a while (asking it nothing), and asks it again once the pause is over', async () => {
    let hang = true
    const { search, asked, clock } = searcher((_url, init) => hang
      ? new Promise<Response>((_resolve, reject) => init.signal!.addEventListener('abort', () => reject(new DOMException('timed out', 'TimeoutError'))))
      : photon(BAD_TOELZ), { timeoutMs: 20 })
    await expect(search.search('bad tölz', 'de')).rejects.toMatchObject({ status: 504, type: 'urn:wetterdienst:problem:places-timeout' })
    expect(asked).toHaveLength(1)
    // resting: the next text is answered a problem at once, and Photon is not asked
    await expect(search.search('bad bayern', 'de')).rejects.toMatchObject({ status: 503, type: 'urn:wetterdienst:problem:places-unavailable' })
    expect(asked).toHaveLength(1)
    hang = false
    clock.now += 10_001
    expect((await search.search('bad bayern', 'de')).length).toBe(1)
    expect(asked).toHaveLength(2)
  })

  it('treats a 429 or 403 of Photon as a refusal and leaves it alone for a minute, and any other status as a failure for ten seconds', async () => {
    for (const [status, seconds] of [[429, 60], [403, 60], [500, 10], [502, 10]] as const) {
      const { search, asked, clock } = searcher(() => new Response('no', { status }))
      await expect(search.search('bad tölz', 'de')).rejects.toMatchObject({ status: status === 429 || status === 403 ? 503 : 502 })
      await expect(search.search('bad other', 'de')).rejects.toMatchObject({ status: 503, retryAfter: seconds })
      expect(asked, String(status)).toHaveLength(1)
      clock.now += seconds * 1000 + 1
      await expect(search.search('bad other', 'de')).rejects.toBeDefined()
      expect(asked, String(status)).toHaveLength(2)
    }
  })

  it('keeps no failure in its cache: a text that failed is asked again after the pause', async () => {
    let fail = true
    const { search, asked, clock } = searcher(() => fail ? new Response('no', { status: 500 }) : photon(BAD_TOELZ))
    await expect(search.search('bad tölz', 'de')).rejects.toBeDefined()
    fail = false
    clock.now += 10_001
    expect((await search.search('bad tölz', 'de')).length).toBe(1)
    expect(search.cacheSize).toBe(1)
    expect(asked).toHaveLength(2)
  })

  it('answers what is not Photon\'s as a 502: a page, text that is not JSON, JSON with no features', async () => {
    const answers = [
      () => new Response('<html>down</html>', { headers: { 'content-type': 'text/html' } }),
      () => new Response('not json', { headers: { 'content-type': 'application/json' } }),
      () => new Response(JSON.stringify({ message: 'hello' }), { headers: { 'content-type': 'application/json' } }),
      () => new Response(JSON.stringify({ features: 'many' }), { headers: { 'content-type': 'application/json' } }),
    ]
    for (const answer of answers) {
      const { search } = searcher(answer)
      await expect(search.search('bad tölz', 'de')).rejects.toMatchObject({ status: 502, type: 'urn:wetterdienst:problem:places-unexpected-answer' })
    }
  })

  it('answers a connection that cannot be made as a 502, without the text in the log', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { search } = searcher(() => {
      throw new TypeError('fetch failed bad tölz')
    })
    await expect(search.search('bad tölz', 'de')).rejects.toMatchObject({ status: 502, type: 'urn:wetterdienst:problem:places-unreachable' })
    expect(JSON.stringify(warn.mock.calls)).not.toContain('tölz')
    warn.mockRestore()
  })

  it('answers no place for a text Photon has no hit for, and keeps that for a day too', async () => {
    const { search, asked } = searcher(() => photon())
    expect(await search.search('zzzzz', 'en')).toEqual([])
    expect(await search.search('zzzzz', 'en')).toEqual([])
    expect(asked).toHaveLength(1)
  })

  it('stops waiting for its turn when the asker has gone, and then does not ask Photon at all', async () => {
    const clock = { now: 1 }
    const fetcher = vi.fn(async () => photon(BAD_TOELZ))
    const search = createPlacesSearch({
      fetcher: fetcher as unknown as typeof fetch,
      now: () => clock.now,
      sleep: (ms, signal) => new Promise<void>((resolve) => {
        if (ms > 0)
          signal?.addEventListener('abort', () => resolve())
        else
          resolve()
      }),
    })
    await search.search('bad one', 'de')
    const controller = new AbortController()
    const waiting = search.search('bad two', 'de', controller.signal)
    controller.abort()
    await expect(waiting).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})

describe('the route', () => {
  const servers: Server[] = []
  afterEach(async () => {
    await Promise.all(servers.splice(0).map(server => new Promise(resolve => server.close(resolve))))
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  /** A server with the route on it, the runtime config as the test says, and the stand-in for Photon, which records what it was asked with */
  async function serve(config: Record<string, unknown> = {}, answer: (url: URL, init: RequestInit) => Response | Promise<Response> = () => photon(BAD_TOELZ)) {
    for (const [name, value] of Object.entries({
      defineEventHandler: h3.defineEventHandler,
      getQuery: h3.getQuery,
      getRequestHeader: h3.getRequestHeader,
      setResponseHeader: h3.setResponseHeader,
      setResponseStatus: h3.setResponseStatus,
      useRuntimeConfig: () => ({ placesSearch: 'on', placesPhotonBase: 'http://photon.stand-in/api/', ...config }),
    }))
      vi.stubGlobal(name, value)
    const asked: Array<{ url: URL, init: RequestInit }> = []
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      asked.push({ url: new URL(url as URL), init: init! })
      return answer(new URL(url as URL), init!)
    })
    const app = h3.createApp()
    app.use(placesSearchHandler({ fetcher: fetcher as unknown as typeof fetch, sleep: async () => {} }))
    const server = createServer(h3.toNodeListener(app))
    servers.push(server)
    const origin = await new Promise<string>(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
    return { asked, get: (query: string, headers: Record<string, string> = {}, signal?: AbortSignal) => fetch(`${origin}/?${query}`, { headers, signal }) }
  }

  it('answers the places of a text, with the credit that OpenStreetMap\'s licence asks for, from the address in the runtime config', async () => {
    const { asked, get } = await serve()
    const response = await get('q=bad%20t%C3%B6lz&lang=de')
    expect(response.status).toBe(200)
    const answer = await response.json() as PlacesAnswer
    expect(answer).toEqual({ query: 'bad tölz', state: 'ok', places: [expect.objectContaining({ name: 'Bad Tölz', kind: 'town', latitude: 47.7614, longitude: 11.5583 })], attribution: PLACES_ATTRIBUTION })
    expect(response.headers.get('cache-control')).toBe('private, max-age=300')
    expect(response.headers.get('x-request-id')).toBeTruthy()
    expect(`${asked[0]!.url.origin}${asked[0]!.url.pathname}`).toBe('http://photon.stand-in/api/')
  })

  it('passes nothing of the client to Photon: not its address, its cookies, its referrer, its language or any header it sends', async () => {
    const { asked, get } = await serve()
    await get('q=bad%20t%C3%B6lz&lang=de', {
      'x-forwarded-for': '203.0.113.7',
      'x-real-ip': '203.0.113.7',
      'forwarded': 'for=203.0.113.7',
      'cookie': 'wd_lang=de',
      'referer': 'https://wetterdienst.eobs.org/map',
      'origin': 'https://wetterdienst.eobs.org',
      'accept-language': 'de-DE,de;q=0.9',
      'authorization': 'Bearer secret',
      'user-agent': 'Mozilla/5.0 (a reader\'s browser)',
      'x-request-id': 'abc123',
    })
    expect(asked).toHaveLength(1)
    const headers = Object.fromEntries(Object.entries(asked[0]!.init.headers as Record<string, string>).map(([name, value]) => [name.toLowerCase(), value]))
    expect(Object.keys(headers).sort()).toEqual(['accept', 'user-agent'])
    expect(headers['user-agent']).toBe(PLACES_USER_AGENT)
    // and nothing of it in the address either: the text, the language, the limit
    expect(JSON.stringify([...asked[0]!.url.searchParams])).not.toMatch(/203\.0\.113|wd_lang|Mozilla|secret/)
    expect([...asked[0]!.url.searchParams.keys()].sort()).toEqual(['lang', 'limit', 'q'])
  })

  it('is switched off by `NUXT_PLACES_SEARCH=off` (and by any other text but the words for on): `state: off`, no place, nothing asked of Photon, nothing kept', async () => {
    for (const setting of ['off', 'false', 'typo']) {
      const { asked, get } = await serve({ placesSearch: setting })
      const response = await get('q=bad%20t%C3%B6lz&lang=de')
      expect(response.status, setting).toBe(200)
      expect(await response.json()).toEqual({ query: 'bad tölz', state: 'off', places: [], attribution: PLACES_ATTRIBUTION })
      expect(response.headers.get('cache-control')).toBe('no-store')
      expect(asked, setting).toEqual([])
    }
    // a switched-off search needs no valid text: the palette learns it from the first request, whatever it was
    const { get } = await serve({ placesSearch: 'off' })
    expect(((await (await get('q=ab')).json()) as PlacesAnswer).state).toBe('off')
  })

  it('answers an invalid request as a 422 problem, as the backend does, and asks Photon nothing', async () => {
    const { asked, get } = await serve()
    for (const query of ['', 'q=ab', 'q=52.5%2C13.4', `q=${'x'.repeat(101)}`, 'q=paris&lang=de%3Bdrop']) {
      const response = await get(query)
      expect(response.status, query).toBe(422)
      expect(response.headers.get('content-type')).toContain('application/problem+json')
      expect(response.headers.get('cache-control')).toBe('no-store')
      const problem = await response.json()
      expect(problem).toMatchObject({ type: 'urn:wetterdienst:problem:invalid-parameters', status: 422 })
      expect(problem.request_id).toBeTruthy()
      expect(problem.instance).toBe(`urn:wetterdienst:request:${problem.request_id}`)
      expect(problem.errors[0].loc[0]).toBe('query')
    }
    expect(asked).toEqual([])
  })

  it('answers a failure of Photon as a problem with its status, a Retry-After where there is a time to wait, and the id of the request, and no answer is cached', async () => {
    const { get } = await serve({}, () => new Response('too many', { status: 429 }))
    const refused = await get('q=bad%20t%C3%B6lz&lang=de', { 'x-request-id': 'req-1' })
    expect(refused.status).toBe(503)
    expect(refused.headers.get('content-type')).toContain('application/problem+json')
    expect(refused.headers.get('retry-after')).toBe('60')
    expect(refused.headers.get('cache-control')).toBe('no-store')
    expect(await refused.json()).toMatchObject({ type: 'urn:wetterdienst:problem:places-busy', status: 503, request_id: 'req-1', instance: 'urn:wetterdienst:request:req-1' })
    // resting: the next one is answered at once from here
    const resting = await get('q=paris&lang=en')
    expect(resting.status).toBe(503)
    expect((await resting.json()).type).toBe('urn:wetterdienst:problem:places-unavailable')
  })

  it('stops asking Photon for a client that has gone, where nobody else waits for the same text', async () => {
    let asking: AbortSignal | undefined
    const { get } = await serve({}, (_url, init) => new Promise<Response>((_resolve, reject) => {
      asking = init.signal!
      init.signal!.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    const client = new AbortController()
    const gone = get('q=bad%20t%C3%B6lz&lang=de', {}, client.signal).catch(() => 'gone')
    await vi.waitFor(() => expect(asking).toBeDefined())
    expect(asking!.aborted).toBe(false)
    client.abort()
    expect(await gone).toBe('gone')
    await vi.waitFor(() => expect(asking!.aborted).toBe(true))
  })

  it('answers a Photon that does not answer in time as a 504 problem', async () => {
    const { get } = await serve({}, (_url, init) => new Promise<Response>((_resolve, reject) => init.signal!.addEventListener('abort', () => reject(new DOMException('timed out', 'TimeoutError')))))
    // the real timeout is four seconds
    const response = await get('q=bad%20t%C3%B6lz&lang=de')
    expect(response.status).toBe(504)
    expect((await response.json()).type).toBe('urn:wetterdienst:problem:places-timeout')
  }, 10_000)
})

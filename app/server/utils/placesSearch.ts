import type { PlaceMatch, PlacesAnswer } from '../../shared/utils/places'
import { isPlaceQuery, MAX_PLACE_QUERY, MAX_PLACES, MIN_PLACE_QUERY, normalisePlaceQuery, photonLang, PLACES_ATTRIBUTION, placesOfPhoton } from '../../shared/utils/places'
import { requestIdOf } from './requestId'
import { AbortedError, TtlCache } from './ttlCache'

// The places the search of the header finds by name (GH-3790, GH-3791): `GET /_search/places?q=bad%20tölz&lang=de` asks Photon
// (photon.komoot.io, a search of OpenStreetMap's data run by komoot) for them, from this server, and answers the few that the search shows.
//
// Why here and not in the browser: the browser would send the reader's address, the time and its own details to komoot with every
// keystroke; asked from here, komoot sees this server and the text, and nothing of the reader. What it sends is the text, the language
// and a limit, with a User-Agent that names the project and where to reach it (Photon's own page asks for no more than being fair: "extensive
// usage will be throttled", no limit is stated and no availability is promised). None of the reader's headers, address or cookies is passed on.
//
// Being fair is done here, in four ways:
// - the answers are kept for a day, by the text (case and spaces ignored) and the language, so a place that many readers look for is asked for once;
// - the requests to Photon are paced for the whole app, whoever asks (`PLACES_PER_SECOND`): one that would wait longer than `PLACES_MAX_WAIT_MS` is refused
//   (a 503 with `Retry-After`, which the palette says) and not queued up;
// - a request that Photon does not answer in time, or answers with a refusal (429, 403) or a failure, is followed by a pause in which Photon is not asked at
//   all (`COOLDOWN_MS`), and the problem is answered at once from here;
// - the app's own limit for each client (`server/utils/rateLimit.ts`) counts these requests like the other routes of `/_search`.
//
// The operator can switch the search off (`NUXT_PLACES_SEARCH=off`): the route then answers `state: 'off'` and asks Photon nothing, and the palette
// shows no group of places. Nothing of a request is logged here: not the text, not the address (a failure logs the name of its error).

export const PLACES_PHOTON_BASE = 'https://photon.komoot.io/api/'
/** Who is asking, for komoot: the project's page */
export const PLACES_CONTACT_URL = 'https://github.com/earthobservations/wetterdienst'
export const PLACES_USER_AGENT = `wetterdienst-app (+${PLACES_CONTACT_URL})`

/** How long an answer is kept, and how many are: a few thousand names of places are a few MB */
export const PLACES_CACHE_TTL_MS = 24 * 3_600_000
export const PLACES_CACHE_ENTRIES = 5000
/** How many requests to Photon the app makes in a second at most, in all */
export const PLACES_PER_SECOND = 3
/** How long a request waits for its turn before it is refused, and how long Photon has to answer */
export const PLACES_MAX_WAIT_MS = 1500
export const PLACES_TIMEOUT_MS = 4000
/** How long Photon is left alone after a refusal (429 or 403), and after any other failure */
export const PLACES_REFUSED_COOLDOWN_MS = 60_000
export const PLACES_FAILED_COOLDOWN_MS = 10_000
/** How many hits are asked for: the search shows `MAX_PLACES` places, and streets and shops among the hits are left out */
export const PLACES_PHOTON_LIMIT = 12
/** The longest answer that is read */
const MAX_BODY_BYTES = 1_000_000

/** The values of `NUXT_PLACES_SEARCH` that leave the search on; the default is on, and any other text switches it off, so that a typing mistake never leaves it running */
const ON = new Set(['on', 'true', '1', 'yes', 'enabled'])
export function placesSearchOn(setting: unknown): boolean {
  if (setting === undefined || setting === null || setting === '')
    return true
  return ON.has(String(setting).trim().toLowerCase())
}

/** What the route answers where it cannot give the places: a problem with its status */
export class PlacesError extends Error {
  constructor(readonly status: number, readonly type: string, readonly title: string, detail: string, readonly retryAfter?: number) {
    super(detail)
    this.name = 'PlacesError'
  }
}

export interface PlacesSearchOptions {
  /** Where Photon's API is (`NUXT_PLACES_PHOTON_BASE`, which the end-to-end tests point at a stand-in) */
  photonBase?: () => string
  fetcher?: typeof fetch
  now?: () => number
  perSecond?: number
  maxWaitMs?: number
  timeoutMs?: number
  /** Waits `ms`, or fewer where `signal` aborts; the tests make it instant */
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>
  ttlMs?: number
  maxEntries?: number
}

function defaultSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (ms <= 0 || signal?.aborted)
      return resolve()
    const timer = setTimeout(done, ms)
    function done() {
      clearTimeout(timer)
      signal?.removeEventListener('abort', done)
      resolve()
    }
    signal?.addEventListener('abort', done, { once: true })
  })
}

/** The key an answer is kept under: the text as one line in lower case, and the language */
export function placesCacheKey(query: string, lang: string): string {
  return `${lang}|${normalisePlaceQuery(query).toLowerCase()}`
}

/**
 * The search of places: the cache, the pace and the pause towards Photon, and the one request. `search` gives the places or throws a `PlacesError`.
 */
export function createPlacesSearch(options: PlacesSearchOptions = {}) {
  const photonBase = options.photonBase ?? (() => PLACES_PHOTON_BASE)
  const fetcher = options.fetcher ?? globalThis.fetch
  const now = options.now ?? Date.now
  const interval = 1000 / (options.perSecond ?? PLACES_PER_SECOND)
  const maxWaitMs = options.maxWaitMs ?? PLACES_MAX_WAIT_MS
  const timeoutMs = options.timeoutMs ?? PLACES_TIMEOUT_MS
  const sleep = options.sleep ?? defaultSleep
  const cache = new TtlCache<PlaceMatch[]>({ ttlMs: options.ttlMs ?? PLACES_CACHE_TTL_MS, maxEntries: options.maxEntries ?? PLACES_CACHE_ENTRIES, now })

  /** The time the next request to Photon may go at, which the pace moves on, and the time before which Photon is not asked after a failure */
  let nextSlot = 0
  let pausedUntil = 0

  /** The time to wait for a turn, or null where it is too long (the slot is then not taken) */
  function reserve(): number | null {
    const at = Math.max(now(), nextSlot)
    if (at - now() > maxWaitMs)
      return null
    nextSlot = at + interval
    return at - now()
  }

  function pause(ms: number) {
    pausedUntil = Math.max(pausedUntil, now() + ms)
  }

  async function ask(query: string, lang: string, signal: AbortSignal): Promise<PlaceMatch[]> {
    const paused = pausedUntil - now()
    if (paused > 0)
      throw new PlacesError(503, 'urn:wetterdienst:problem:places-unavailable', 'Service Unavailable', 'The place search is resting after a failure of its source. Try again in a moment.', Math.ceil(paused / 1000))
    const wait = reserve()
    if (wait === null)
      throw new PlacesError(503, 'urn:wetterdienst:problem:places-busy', 'Service Unavailable', 'The place search is asked for too often just now. Try again in a moment.', 1)
    await sleep(wait, signal)
    if (signal.aborted)
      throw new AbortedError()
    const url = new URL(photonBase())
    url.searchParams.set('q', query)
    url.searchParams.set('lang', lang)
    url.searchParams.set('limit', String(PLACES_PHOTON_LIMIT))
    const limit = AbortSignal.timeout(timeoutMs)
    let response: Response
    try {
      // the text, the language and a limit: nothing of the reader. The headers are these two, and no others.
      response = await fetcher(url, { headers: { 'user-agent': PLACES_USER_AGENT, 'accept': 'application/json' }, signal: AbortSignal.any([signal, limit]), redirect: 'error' })
    }
    catch (failure) {
      if (signal.aborted)
        throw new AbortedError()
      pause(PLACES_FAILED_COOLDOWN_MS)
      if (limit.aborted)
        throw new PlacesError(504, 'urn:wetterdienst:problem:places-timeout', 'Gateway Timeout', `The place search did not answer within ${timeoutMs / 1000} seconds.`)
      console.warn('place search: Photon could not be reached:', (failure as Error)?.name)
      throw new PlacesError(502, 'urn:wetterdienst:problem:places-unreachable', 'Bad Gateway', 'The place search could not be reached.')
    }
    if (response.status === 429 || response.status === 403) {
      pause(PLACES_REFUSED_COOLDOWN_MS)
      await response.body?.cancel().catch(() => {})
      throw new PlacesError(503, 'urn:wetterdienst:problem:places-busy', 'Service Unavailable', 'The place search refuses requests just now. Try again later.', Math.ceil(PLACES_REFUSED_COOLDOWN_MS / 1000))
    }
    if (!response.ok) {
      pause(PLACES_FAILED_COOLDOWN_MS)
      await response.body?.cancel().catch(() => {})
      throw new PlacesError(502, 'urn:wetterdienst:problem:places-unexpected-answer', 'Bad Gateway', `The place search answered with status ${response.status}.`)
    }
    let body: unknown
    try {
      if (!/json/i.test(response.headers.get('content-type') ?? ''))
        throw new Error('not JSON')
      const raw = await response.text()
      if (raw.length > MAX_BODY_BYTES)
        throw new Error('too long')
      body = JSON.parse(raw)
    }
    catch {
      if (signal.aborted)
        throw new AbortedError()
      pause(PLACES_FAILED_COOLDOWN_MS)
      throw new PlacesError(502, 'urn:wetterdienst:problem:places-unexpected-answer', 'Bad Gateway', 'The place search did not answer with places.')
    }
    const places = placesOfPhoton(body, MAX_PLACES)
    if (places === null)
      throw new PlacesError(502, 'urn:wetterdienst:problem:places-unexpected-answer', 'Bad Gateway', 'The place search did not answer with places.')
    return places
  }

  return {
    /** The places for a text in a language of Photon's, from the cache or from Photon; `signal` is the asker's: leaving stops the wait */
    search(query: string, lang: string, signal?: AbortSignal): Promise<PlaceMatch[]> {
      const normal = normalisePlaceQuery(query)
      return cache.get(placesCacheKey(normal, lang), load => ask(normal, lang, load), signal)
    },
    get cacheSize() {
      return cache.size
    },
  }
}

export interface PlacesQuery {
  q: string
  lang: string
}

interface ParseErrors { errors: Array<{ loc: string[], msg: string }> }

/** What a request names, or the 422 problem's errors: the text (3 to 100 characters, with a letter) and a language, which is `en` where it is not one of Photon's */
export function parsePlacesQuery(query: Record<string, unknown>): PlacesQuery | ParseErrors {
  const errors: ParseErrors['errors'] = []
  const q = typeof query.q === 'string' ? normalisePlaceQuery(query.q) : ''
  if (!q)
    errors.push({ loc: ['query', 'q'], msg: 'Field required' })
  else if ([...q].length > MAX_PLACE_QUERY)
    errors.push({ loc: ['query', 'q'], msg: `Input should have at most ${MAX_PLACE_QUERY} characters` })
  else if (!isPlaceQuery(q))
    errors.push({ loc: ['query', 'q'], msg: `Input should have at least ${MIN_PLACE_QUERY} characters, with a letter among them` })
  let lang = 'en'
  if (query.lang !== undefined && query.lang !== '') {
    if (typeof query.lang !== 'string' || !/^[a-z]{2,3}(?:[-_][a-z0-9]{2,8})*$/i.test(query.lang))
      errors.push({ loc: ['query', 'lang'], msg: 'Input should be a language code such as \'de\' or \'en\'' })
    else
      lang = photonLang(query.lang)
  }
  return errors.length ? { errors } : { q, lang }
}

/** The handler of `GET /_search/places?q=&lang=` */
export function placesSearchHandler(options: PlacesSearchOptions = {}) {
  const { search } = createPlacesSearch({ photonBase: () => String(useRuntimeConfig().placesPhotonBase || PLACES_PHOTON_BASE), ...options })
  return defineEventHandler(async (event) => {
    const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
    setResponseHeader(event, 'x-request-id', requestId)
    const problem = (status: number, type: string, title: string, detail: string, extra: Record<string, unknown> = {}) => {
      setResponseStatus(event, status)
      setResponseHeader(event, 'content-type', 'application/problem+json')
      setResponseHeader(event, 'cache-control', 'no-store')
      return { type, title, status, detail, instance: `urn:wetterdienst:request:${requestId}`, request_id: requestId, ...extra }
    }
    const raw = getQuery(event)
    // switched off by the operator: nothing is asked of anyone, and the palette shows no group
    if (!placesSearchOn(useRuntimeConfig(event).placesSearch)) {
      setResponseHeader(event, 'cache-control', 'no-store')
      return { query: typeof raw.q === 'string' ? normalisePlaceQuery(raw.q) : '', state: 'off', places: [], attribution: PLACES_ATTRIBUTION } satisfies PlacesAnswer
    }
    const parsed = parsePlacesQuery(raw)
    if ('errors' in parsed) {
      return problem(422, 'urn:wetterdienst:problem:invalid-parameters', 'Unprocessable Content', parsed.errors.map(error => `${error.loc.slice(1).join('.')}: ${error.msg}`).join('\n'), { errors: parsed.errors })
    }
    // a client that goes away stops the wait for its answer (and the request to Photon, if nobody else is waiting for it)
    const gone = new AbortController()
    const { res } = event.node
    res.once('close', () => {
      if (!res.writableFinished)
        gone.abort()
    })
    try {
      const places = await search(parsed.q, parsed.lang, gone.signal)
      setResponseHeader(event, 'cache-control', 'private, max-age=300')
      return { query: parsed.q, state: 'ok', places, attribution: PLACES_ATTRIBUTION } satisfies PlacesAnswer
    }
    catch (failure) {
      if (failure instanceof PlacesError) {
        if (failure.retryAfter)
          setResponseHeader(event, 'retry-after', failure.retryAfter)
        return problem(failure.status, failure.type, failure.title, failure.message)
      }
      if (failure instanceof AbortedError)
        return problem(499, 'urn:wetterdienst:problem:client-closed-request', 'Client Closed Request', 'The request ended before the answer was ready.')
      console.error('place search failed:', (failure as Error)?.name)
      return problem(502, 'urn:wetterdienst:problem:places-unexpected-answer', 'Bad Gateway', 'The place search failed. The cause is in the server log.')
    }
  })
}

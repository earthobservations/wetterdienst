import type { PlaceMatch, PlacesAnswer } from '../../shared/utils/places'
import { isPlaceQuery, MAX_PLACE_QUERY, MAX_PLACES, MIN_PLACE_QUERY, normalisePlaceQuery, photonLang, PLACES_ATTRIBUTION, placesOfPhoton } from '../../shared/utils/places'
import { clientKey } from './rateLimit'
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
// Being fair is done here, in five ways:
// - the answers are kept for a day, by the text (case and spaces ignored) and the language, so a place that many readers look for is asked for once;
// - the requests to Photon are paced for the whole app, whoever asks (`PLACES_PER_SECOND`): one that would wait longer than `PLACES_MAX_WAIT_MS` is refused
//   (a 503 with `Retry-After`, which the palette says) and not queued up;
// - a request that Photon does not answer in time, or answers with a refusal (429, 403, for as long as its `Retry-After` says, else a minute) or a
//   failure, is followed by a pause in which Photon is not asked at all, and the problem is answered at once from here, also for the requests that
//   were waiting for their turn when it began;
// - each client has a share of the requests to Photon (a few at once, then one a second), which the answers of the cache do not use up, so that one
//   client cannot use up the pace of all;
// - the app's own limit for each client (`server/utils/rateLimit.ts`) counts these requests in the one bucket of every data route, like the other
//   routes of `/_search`.
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
/** The longest answer that is read, in bytes */
export const PLACES_MAX_BODY_BYTES = 1_000_000
/** The longest a `Retry-After` of Photon's is followed */
export const PLACES_REFUSED_MAX_COOLDOWN_MS = 600_000
/** The share of the requests to Photon that one client may use up: a few at once, then one a second */
export const PLACES_CLIENT_BURST = 3
export const PLACES_CLIENT_PER_SECOND = 1

/** The values of `NUXT_PLACES_SEARCH` that leave the search on and that switch it off; the default is on, and any other text switches it off too (and is warned of at start), so that a typing mistake never leaves it running */
const ON = new Set(['on', 'true', '1', 'yes', 'enabled'])
const OFF = new Set(['off', 'false', '0', 'no', 'disabled'])
export function placesSearchSetting(setting: unknown): 'on' | 'off' | 'unrecognised' {
  if (setting === undefined || setting === null || setting === '')
    return 'on'
  const word = String(setting).trim().toLowerCase()
  return ON.has(word) ? 'on' : OFF.has(word) ? 'off' : 'unrecognised'
}
export function placesSearchOn(setting: unknown): boolean {
  return placesSearchSetting(setting) === 'on'
}

/** The line to log once at start for a value of `NUXT_PLACES_SEARCH` that is neither on nor off, else undefined: the search is off then */
export function placesSearchWarning(setting: unknown): string | undefined {
  return placesSearchSetting(setting) === 'unrecognised'
    ? `NUXT_PLACES_SEARCH=${JSON.stringify(String(setting))} is not one of on, true, 1, yes, enabled (on) or off, false, 0, no, disabled (off): the place search is switched off.`
    : undefined
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
  /** The share of one client of the requests to Photon (`PLACES_CLIENT_BURST`, `PLACES_CLIENT_PER_SECOND`) */
  clientBurst?: number
  clientPerSecond?: number
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

/** The seconds a `Retry-After` header names (a number of seconds or a date), or null where it names none; at most `PLACES_REFUSED_MAX_COOLDOWN_MS` */
export function retryAfterSeconds(header: string | null, nowMs: number): number | null {
  if (!header)
    return null
  const seconds = /^\d+$/.test(header.trim()) ? Number(header.trim()) : /[a-z]/i.test(header) ? (Date.parse(header) - nowMs) / 1000 : Number.NaN
  if (!Number.isFinite(seconds) || seconds < 0)
    return null
  return Math.min(Math.max(1, Math.ceil(seconds)), PLACES_REFUSED_MAX_COOLDOWN_MS / 1000)
}

/** The text of an answer, read as bytes and given up past `max` of them (the declared size, else what has arrived) */
async function readCapped(response: Response, max: number): Promise<string> {
  const declared = Number(response.headers.get('content-length'))
  if (Number.isFinite(declared) && declared > max)
    throw new Error('too long')
  const reader = response.body?.getReader()
  if (!reader)
    return ''
  const chunks: Uint8Array<ArrayBuffer>[] = []
  let size = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done)
      break
    size += value.byteLength
    if (size > max) {
      await reader.cancel().catch(() => {})
      throw new Error('too long')
    }
    chunks.push(value as Uint8Array<ArrayBuffer>)
  }
  return new Blob(chunks).text()
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
  const clientBurst = options.clientBurst ?? PLACES_CLIENT_BURST
  const clientPerSecond = options.clientPerSecond ?? PLACES_CLIENT_PER_SECOND
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

  /** The problem of a pause that is on, or nothing */
  function resting(): PlacesError | null {
    const paused = pausedUntil - now()
    return paused > 0
      ? new PlacesError(503, 'urn:wetterdienst:problem:places-unavailable', 'Service Unavailable', 'The place search is resting after a failure of its source. Try again in a moment.', Math.ceil(paused / 1000))
      : null
  }

  /** What each client has left of its share of the requests to Photon, in memory and for as long as it takes to fill again: a bucket that is full is dropped */
  const shares = new Map<string, { tokens: number, at: number }>()

  /** Takes one request of a client's share (`clientBurst` at once, `clientPerSecond` after), or says in seconds when it has one again */
  function takeShare(client: string): number | null {
    const at = now()
    if (shares.size > 10_000) {
      for (const [other, share] of shares) {
        if (share.tokens + (at - share.at) / 1000 * clientPerSecond >= clientBurst)
          shares.delete(other)
      }
    }
    const share = shares.get(client) ?? { tokens: clientBurst, at }
    const tokens = Math.min(clientBurst, share.tokens + (at - share.at) / 1000 * clientPerSecond)
    if (tokens < 1) {
      shares.set(client, { tokens, at })
      return Math.ceil((1 - tokens) / clientPerSecond)
    }
    shares.set(client, { tokens: tokens - 1, at })
    return null
  }

  /** `signal` is for the wait for a turn only: a request that has been sent is let finish, and its answer kept, whoever is still there to read it */
  async function ask(query: string, lang: string, signal: AbortSignal): Promise<PlaceMatch[]> {
    const before = resting()
    if (before)
      throw before
    const wait = reserve()
    if (wait === null)
      throw new PlacesError(503, 'urn:wetterdienst:problem:places-busy', 'Service Unavailable', 'The place search is asked for too often just now. Try again in a moment.', 1)
    await sleep(wait, signal)
    if (signal.aborted)
      throw new AbortedError()
    // a refusal of Photon's that came while this request waited for its turn: it is not sent
    const after = resting()
    if (after)
      throw after
    const url = new URL(photonBase())
    url.searchParams.set('q', query)
    url.searchParams.set('lang', lang)
    url.searchParams.set('limit', String(PLACES_PHOTON_LIMIT))
    const limit = AbortSignal.timeout(timeoutMs)
    let response: Response
    try {
      // the text, the language and a limit: nothing of the reader. The headers are these two, and no others.
      response = await fetcher(url, { headers: { 'user-agent': PLACES_USER_AGENT, 'accept': 'application/json' }, signal: limit, redirect: 'error' })
    }
    catch (failure) {
      pause(PLACES_FAILED_COOLDOWN_MS)
      if (limit.aborted)
        throw new PlacesError(504, 'urn:wetterdienst:problem:places-timeout', 'Gateway Timeout', `The place search did not answer within ${timeoutMs / 1000} seconds.`)
      console.warn('place search: Photon could not be reached:', (failure as Error)?.name)
      throw new PlacesError(502, 'urn:wetterdienst:problem:places-unreachable', 'Bad Gateway', 'The place search could not be reached.')
    }
    if (response.status === 429 || response.status === 403) {
      // as long as Photon says, else a minute
      const seconds = retryAfterSeconds(response.headers.get('retry-after'), now()) ?? PLACES_REFUSED_COOLDOWN_MS / 1000
      pause(seconds * 1000)
      await response.body?.cancel().catch(() => {})
      throw new PlacesError(503, 'urn:wetterdienst:problem:places-busy', 'Service Unavailable', 'The place search refuses requests just now. Try again later.', seconds)
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
      body = JSON.parse(await readCapped(response, PLACES_MAX_BODY_BYTES))
    }
    catch {
      pause(PLACES_FAILED_COOLDOWN_MS)
      throw new PlacesError(502, 'urn:wetterdienst:problem:places-unexpected-answer', 'Bad Gateway', 'The place search did not answer with places.')
    }
    const places = placesOfPhoton(body, MAX_PLACES)
    if (places === null)
      throw new PlacesError(502, 'urn:wetterdienst:problem:places-unexpected-answer', 'Bad Gateway', 'The place search did not answer with places.')
    return places
  }

  return {
    /**
     * The places for a text in a language of Photon's, from the cache or from Photon; `signal` is the asker's: leaving stops the wait for a turn. A `client`
     * (its address as the rate limit reads it) is held to its share of the requests to Photon, which the answers of the cache do not use up.
     */
    search(query: string, lang: string, signal?: AbortSignal, client?: string): Promise<PlaceMatch[]> {
      const normal = normalisePlaceQuery(query)
      const key = placesCacheKey(normal, lang)
      if (client && !cache.has(key)) {
        const wait = takeShare(client)
        if (wait !== null)
          return Promise.reject(new PlacesError(429, 'urn:wetterdienst:problem:rate-limited', 'Too Many Requests', `This client asked the place search too often. Try again in ${wait} seconds.`, wait))
      }
      return cache.get(key, load => ask(normal, lang, load), signal)
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
    const config = useRuntimeConfig(event)
    // the end-to-end tests ask where this server would send its requests, before they type anything: only where `NUXT_PLACES_E2E=1` says so (they never reach komoot)
    if (raw.probe !== undefined && String(config.placesE2e) === '1') {
      setResponseHeader(event, 'cache-control', 'no-store')
      return { photon_base: String(config.placesPhotonBase || PLACES_PHOTON_BASE) }
    }
    // switched off by the operator: nothing is asked of anyone, and the palette shows no group
    if (!placesSearchOn(config.placesSearch)) {
      setResponseHeader(event, 'cache-control', 'no-store')
      return { query: typeof raw.q === 'string' ? normalisePlaceQuery(raw.q) : '', state: 'off', places: [], attribution: PLACES_ATTRIBUTION } satisfies PlacesAnswer
    }
    const parsed = parsePlacesQuery(raw)
    if ('errors' in parsed) {
      return problem(422, 'urn:wetterdienst:problem:invalid-parameters', 'Unprocessable Content', parsed.errors.map(error => `${error.loc.slice(1).join('.')}: ${error.msg}`).join('\n'), { errors: parsed.errors })
    }
    // a client that goes away stops the wait for its turn; a request to Photon that has been sent is let finish, and its answer is kept
    const gone = new AbortController()
    const { res } = event.node
    res.once('close', () => {
      if (!res.writableFinished)
        gone.abort()
    })
    // the client's share of the requests to Photon is held where the limit of the app is on (the suite's own server switches it off)
    const limits = (config.rateLimit ?? {}) as { enabled?: boolean, clientIpHeader?: string }
    const header = String(limits.clientIpHeader ?? '').trim().toLowerCase()
    const client = limits.enabled === false ? undefined : clientKey(getRequestIP(event), header, header ? getRequestHeader(event, header) : undefined)
    try {
      const places = await search(parsed.q, parsed.lang, gone.signal, client)
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

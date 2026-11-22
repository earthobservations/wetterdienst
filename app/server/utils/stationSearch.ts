import type { PreparedStations, StationMatches, StationSearchAnswer } from '../../app/utils/station-search'
import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import type { GhcnMapList, GhcnProblem, StationSource } from './ghcnStations'
import { prepareStations, reportsThisOrLastYear, searchPrepared } from '../../app/utils/station-search'
import { useApiBase } from './apiBase'
import { createListKeeper, readStationColumns, sharedGhcnMapList } from './ghcnStations'
import { requestIdOf } from './requestId'

// The stations the search of the header finds by name or number (GH-3790): `GET /_search/stations?q=hamburg&limit=4&lists=ghcn,measured`
// matches the query against the lists of the map that the reader chose in the settings ("Stations in the search") and that the server keeps
// in its memory for a day, and answers the best stations of each. The browser asks for a few hundred bytes for a keystroke, and never for a
// list. There are two lists here:
//
// - NOAA GHCN daily (132,894 stations): the one the map's route keeps (`sharedGhcnMapList`, read as a stream of CSV, GH-4299), so that a
//   visit that has used both has made one read of the backend.
// - DWD's measuring stations (1,284, 0.2 MB of CSV): read the first time a search asks for them, which is when a reader has turned them on,
//   through the same streamed reader.
//
// The forecast's points (DWD MOSMIX) are not kept here: the palette asks the backend for them by name, as it always has. A list that is
// not asked for is never read.
//
// The route is not under `/api`, which is the backend's namespace and is proxied to it as it is; it counts against the rate limit of the
// server like the routes of `/_ghcn` (`server/utils/rateLimit.ts`).

/** The stations that measure: DWD's observations, as the map opens with them (`daily/climate_summary`), as the CSV that the streamed reader reads */
export const MEASURED_SOURCE: StationSource = { path: '/stations?provider=dwd&network=observation&parameters=daily/climate_summary&all=true&format=csv', what: 'the measuring stations', network: 'DWD observations', refuseSkipped: true }
/** The lists this route serves, which a request names in `lists` */
export const SERVED_LISTS = ['measured', 'ghcn'] as const
export type ServedList = typeof SERVED_LISTS[number]
/** The fewest stations of DWD's measuring stations that are kept: the list has 1,284, and a part of it (the backend's cold start, a provider that failed) is not the list for a day; a file the backend skipped is refused by its warning besides */
export const MIN_SEARCH_STATIONS = 1000

/** How long the search waits for a list that is being made, in milliseconds; past it the answer is without that list's stations, and says it is still being read */
const WAIT_FOR_LIST_MS = 5000
/** The most stations of a network that one request may ask for */
export const MAX_LIMIT = 10
export const DEFAULT_LIMIT = 4
/** The longest query that is searched: a name, an id, a few words */
export const MAX_QUERY_LENGTH = 100

export interface StationSearchOptions {
  apiBase?: () => string
  fetcher?: typeof fetch
  now?: () => number
  /** The GHCN list, where a test stands in for it; the shared one by default */
  ghcn?: GhcnMapList
  minimum?: number
  /** How long a list that is being made is waited for */
  waitMs?: number
}

type Outcome = { kind: 'matches', matches: StationMatches } | { kind: 'pending' } | { kind: 'failed' }

/** What the search is given for each list: a way to ask for it, prepared */
interface SearchList {
  network: ServedList
  prepared: (requestId: string) => Promise<PreparedStations | 'pending' | GhcnProblem>
}

/**
 * The two lists the server matches, GHCN daily (the map's own list) and DWD's measuring stations, each kept as the map's list is
 * (`createListKeeper`), prepared once (names folded) when it is made. One that cannot be read does not take the other with it.
 */
export function createStationSearch(options: StationSearchOptions = {}) {
  const apiBase = options.apiBase ?? useApiBase
  const now = options.now ?? Date.now
  const waitMs = options.waitMs ?? WAIT_FOR_LIST_MS
  const minimum = options.minimum ?? MIN_SEARCH_STATIONS
  const reporting = reportsThisOrLastYear(now)

  function ownList(network: ServedList, source: StationSource): SearchList {
    const keeper = createListKeeper({
      now: options.now,
      what: source.what,
      read: async (requestId) => {
        const read = await readStationColumns(apiBase(), source, requestId, options.fetcher, minimum)
        return 'body' in read ? read : prepareStations(read, reporting)
      },
    })
    return {
      network,
      prepared: async (requestId) => {
        const answer = await keeper.get(requestId, { waitMs })
        return 'kept' in answer ? answer.kept.value : 'pending' in answer ? 'pending' : answer.problem
      },
    }
  }

  // the GHCN list is the map's, whose entry has the columns: folded once for each list that is made
  const ghcn = options.ghcn ?? sharedGhcnMapList
  const folded = new WeakMap<GhcnStationColumns, PreparedStations>()
  const ghcnList: SearchList = {
    network: 'ghcn',
    prepared: async (requestId) => {
      const answer = await ghcn.get(requestId, { waitMs })
      if (!('kept' in answer))
        return 'pending' in answer ? 'pending' : answer.problem
      const { columns } = answer.kept.value
      let list = folded.get(columns)
      if (!list) {
        list = prepareStations(columns, reporting)
        folded.set(columns, list)
      }
      return list
    },
  }

  const all: Record<ServedList, SearchList> = { ghcn: ghcnList, measured: ownList('measured', MEASURED_SOURCE) }

  /**
   * The best `limit` stations of each list asked for, for a query. A list whose reading is not done is `pending` (the caller asks again
   * in a moment) and one that could not be read `failed`; the others answer. A list that is not asked for is not read.
   */
  async function search(query: string, limit: number, requestId: string, asked: readonly ServedList[] = SERVED_LISTS): Promise<StationSearchAnswer> {
    const lists = SERVED_LISTS.filter(name => asked.includes(name)).map(name => all[name])
    const outcomes = await Promise.all(lists.map(async (list): Promise<Outcome> => {
      const prepared = await list.prepared(requestId)
      if (prepared === 'pending')
        return { kind: 'pending' }
      if ('body' in prepared)
        return { kind: 'failed' }
      return { kind: 'matches', matches: searchPrepared(prepared, query, limit) }
    }))
    const answer: StationSearchAnswer = { query, networks: [], pending: [], failed: [] }
    lists.forEach((list, index) => {
      const outcome = outcomes[index]!
      if (outcome.kind === 'pending')
        answer.pending.push(list.network)
      else if (outcome.kind === 'failed')
        answer.failed.push(list.network)
      else if (outcome.matches.total > 0)
        answer.networks.push({ network: list.network, ...outcome.matches })
    })
    return answer
  }

  return { search }
}

export interface StationSearchQuery {
  q: string
  limit: number
  /** The lists to search, in the order the answer has them */
  lists: ServedList[]
}

/** What a request names, or the problem (a 422, in the shape of the backend's) that says what is wrong with it */
export function parseSearchQuery(query: Record<string, unknown>): StationSearchQuery | { errors: Array<{ loc: string[], msg: string }> } {
  const errors: Array<{ loc: string[], msg: string }> = []
  const q = typeof query.q === 'string' ? query.q.trim() : ''
  if (!q)
    errors.push({ loc: ['query', 'q'], msg: 'Field required' })
  else if (q.length > MAX_QUERY_LENGTH)
    errors.push({ loc: ['query', 'q'], msg: `Input should have at most ${MAX_QUERY_LENGTH} characters` })
  let limit = DEFAULT_LIMIT
  if (query.limit !== undefined && query.limit !== '') {
    const given = typeof query.limit === 'string' && /^\d{1,3}$/.test(query.limit) ? Number(query.limit) : Number.NaN
    if (!(given >= 1 && given <= MAX_LIMIT))
      errors.push({ loc: ['query', 'limit'], msg: `Input should be a whole number from 1 to ${MAX_LIMIT}` })
    else
      limit = given
  }
  // the lists the reader chose: GHCN daily where none is named
  let lists: ServedList[] = ['ghcn']
  if (query.lists !== undefined && query.lists !== '') {
    const named = typeof query.lists === 'string' ? query.lists.split(',') : []
    if (!named.length || named.some(name => !(SERVED_LISTS as readonly string[]).includes(name)))
      errors.push({ loc: ['query', 'lists'], msg: `Input should be a comma-separated list of ${SERVED_LISTS.map(name => `'${name}'`).join(' and ')}` })
    else
      lists = SERVED_LISTS.filter(name => named.includes(name))
  }
  return errors.length ? { errors } : { q, limit, lists }
}

/** The handler of `GET /_search/stations?q=&limit=&lists=` */
export function stationSearchHandler(options: StationSearchOptions = {}) {
  const { search } = createStationSearch(options)
  return defineEventHandler(async (event) => {
    const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
    setResponseHeader(event, 'x-request-id', requestId)
    const parsed = parseSearchQuery(getQuery(event))
    if ('errors' in parsed) {
      setResponseStatus(event, 422)
      setResponseHeader(event, 'content-type', 'application/problem+json')
      setResponseHeader(event, 'cache-control', 'no-store')
      return {
        type: 'urn:wetterdienst:problem:invalid-parameters',
        title: 'Unprocessable Content',
        status: 422,
        detail: parsed.errors.map(error => `${error.loc.slice(1).join('.')}: ${error.msg}`).join('\n'),
        instance: `urn:wetterdienst:request:${requestId}`,
        request_id: requestId,
        errors: parsed.errors,
      }
    }
    const answer = await search(parsed.q, parsed.limit, requestId, parsed.lists)
    // an answer that lacks a list is for now: a browser or a shared cache keeps no copy of it
    setResponseHeader(event, 'cache-control', answer.pending.length || answer.failed.length ? 'no-store' : 'private, max-age=300')
    return answer
  })
}

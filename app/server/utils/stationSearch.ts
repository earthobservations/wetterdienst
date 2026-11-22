import type { PreparedStations, StationMatches, StationSearchAnswer } from '../../app/utils/station-search'
import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import type { GhcnMapList, GhcnProblem, StationSource } from './ghcnStations'
import { prepareStations, searchPrepared } from '../../app/utils/station-search'
import { useApiBase } from './apiBase'
import { createListKeeper, readStationColumns, sharedGhcnMapList } from './ghcnStations'
import { requestIdOf } from './requestId'

// The stations the search of the header finds by name or number (GH-3790): `GET /_search/stations?q=hamburg&limit=4` matches the query
// against the three lists the app shows on its map, which the server keeps in its memory for a day, and answers the best stations of
// each. The browser asks for a few hundred bytes for a keystroke, and never for a list: the forecast's points (5,649, 1.5 MB of the
// backend's JSON), DWD's measuring stations (1,284, 0.5 MB) and NOAA GHCN daily (132,894, 44 MB, which the browser would have to read
// as 2 MB of columns, `/_ghcn/map-stations`, and fold 133k names of). The GHCN list is the one the map's route keeps
// (`sharedGhcnMapList`), so a visit that has used both has made one read of the backend.
//
// The route is not under `/api`, which is the backend's namespace and is proxied to it as it is; it counts against the rate limit of the
// server like the routes of `/_ghcn` (`server/utils/rateLimit.ts`).

/** What a list of stations the search matches is read from: the forecast's points */
export const FORECAST_SOURCE: StationSource = { path: '/stations?provider=dwd&network=mosmix&parameters=hourly/large&all=true', what: 'the forecast stations', network: 'DWD MOSMIX' }
/** The stations that measure: DWD's observations, as the map opens with them (`daily/climate_summary`) */
export const MEASURED_SOURCE: StationSource = { path: '/stations?provider=dwd&network=observation&parameters=daily/climate_summary&all=true', what: 'the measuring stations', network: 'DWD observations' }
/** The fewest stations of one of these lists that is kept: a part of a list (the backend's cold start, a provider that failed) is not the list for a day */
export const MIN_SEARCH_STATIONS = 500

/** How long the search waits for a list that is being made, in milliseconds; past it the answer is without that list's stations, and says it is still being read */
const WAIT_FOR_LIST_MS = 5000
/** The most stations of a network that one request may ask for */
export const MAX_LIMIT = 10
export const DEFAULT_LIMIT = 4
/** The longest query that is searched: a name, an id, a few words */
export const MAX_QUERY_LENGTH = 100

/** The year a station last reported in is this year or last: the rule of the map's GHCN layer (`ghcnReportingRule`), which the lists of the search are given, as they have years and no clock */
function reportsIn(now: () => number): (lastYear: number | null) => boolean {
  return (lastYear) => {
    const threshold = new Date(now()).getUTCFullYear() - 1
    return lastYear === null || lastYear >= threshold
  }
}

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

/** What `searchLists` is given for each network: a way to ask for the list, prepared */
interface SearchList {
  network: 'forecast' | 'measured' | 'ghcn'
  prepared: (requestId: string) => Promise<PreparedStations | 'pending' | GhcnProblem>
}

/**
 * The three lists the search matches, each kept as the map's list of GHCN daily is (`createListKeeper`), prepared once (names folded) when
 * it is made. One that cannot be read does not take the others with it.
 */
export function createStationSearch(options: StationSearchOptions = {}) {
  const apiBase = options.apiBase ?? useApiBase
  const now = options.now ?? Date.now
  const waitMs = options.waitMs ?? WAIT_FOR_LIST_MS
  const minimum = options.minimum ?? MIN_SEARCH_STATIONS
  const reporting = reportsIn(now)

  function ownList(network: 'forecast' | 'measured', source: StationSource): SearchList {
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

  const lists: SearchList[] = [ownList('forecast', FORECAST_SOURCE), ownList('measured', MEASURED_SOURCE), ghcnList]

  /**
   * The best `limit` stations of each network for a query. A network whose list is still being read is `pending` (the caller asks again
   * in a moment) and one that could not be read `failed`; the others answer.
   */
  async function search(query: string, limit: number, requestId: string): Promise<StationSearchAnswer> {
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
  return errors.length ? { errors } : { q, limit }
}

/** The handler of `GET /_search/stations?q=&limit=` */
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
    const answer = await search(parsed.q, parsed.limit, requestId)
    // an answer that lacks a list is for now: a browser or a shared cache keeps no copy of it
    setResponseHeader(event, 'cache-control', answer.pending.length || answer.failed.length ? 'no-store' : 'private, max-age=300')
    return answer
  })
}

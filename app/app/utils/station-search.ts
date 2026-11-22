import type { GhcnStationColumns } from '#shared/types/ghcn-stations'
import { fold } from './palette'

// The stations the search of the header finds by name or number (GH-3790): the matching of a query against a list of stations that
// the app's server keeps as columns (`server/utils/stationSearch.ts`), apart from the server so that a test can hold it. The rule is
// the search's own (`fold`: case and accents aside, every word of the query in the name or the id, in any order), and the map's
// (`searchPrepared`): the names that start with the query come first.

/** A list of stations made ready to be searched: the names, ids and WMO numbers folded once (133k names are not to be folded at every keystroke) */
export interface PreparedStations {
  columns: GhcnStationColumns
  /** Each station's name, folded; the text a query is looked for in is the name, the id and the WMO number */
  names: string[]
  /** Each station's name as the lists that have no umlauts write it (`Müller` is `MUELLER`), folded: null where it is the name above */
  spelled: Array<string | null>
  ids: string[]
  wmo: string[]
  /** Whether the station still reports, as the list's rule says (`reporting` of `prepareStations`) */
  reporting: boolean[]
}

/** What one station of a match is: what the search shows of it */
export interface StationMatch {
  station_id: string
  name: string | null
  latitude: number
  longitude: number
  wmo_id: string | null
  first_year: number | null
  last_year: number | null
  reporting: boolean
}

/** The stations that answer a query: how many there are in all, and the best `limit` of them */
export interface StationMatches {
  total: number
  stations: StationMatch[]
}

/** The fewest letters of a query that is looked for in names: shorter is the whole alphabet */
export const MIN_NAME_LETTERS = 3

/**
 * A text folded as the lists of the stations that have no umlauts write one: `ä`, `ö`, `ü` as `ae`, `oe`, `ue` and `ß` as `ss`, which is how
 * the forecast's and NOAA's lists spell `München` (`MUENCHEN`) and DWD's measuring stations do not (`Fuhlsbüttel`). A query is looked for in
 * both spellings, so that `münchen` and `muenchen` find the station of either list.
 */
export function foldSpelled(text: string): string {
  return fold(text.replace(/[äöüß]/gi, letter => ({ ä: 'ae', ö: 'oe', ü: 'ue', ß: 'ss' })[letter.toLowerCase()]!))
}

/**
 * Folds a list of stations once, for {@link searchPrepared} to compare a query with.
 *
 * @param columns - The list, as the server keeps it
 * @param reporting - Whether a station reports: the rule of its list, by its last year
 * @returns The list ready to be searched; it must not change after it
 */
export function prepareStations(columns: GhcnStationColumns, reporting: (lastYear: number | null) => boolean): PreparedStations {
  const names = columns.name.map(name => fold(name ?? ''))
  return {
    columns,
    names,
    spelled: columns.name.map((name, index) => {
      const spelled = foldSpelled(name ?? '')
      return spelled === names[index] ? null : spelled
    }),
    ids: columns.station_id.map(id => fold(id)),
    wmo: columns.wmo_id.map(wmo => fold(wmo ?? '')),
    reporting: columns.last_year.map(year => reporting(year)),
  }
}

/** Whether a text holds every word */
function holdsAll(text: string, words: string[]): boolean {
  for (const word of words) {
    if (!text.includes(word))
      return false
  }
  return true
}

/** The number of a station as it is written in the lists: the WMO number of `1001` is `01001` */
function numberTypedAs(word: string): string {
  return /^\d{1,5}$/.test(word) ? word.padStart(5, '0') : word
}

/**
 * The stations of a list whose name, id or WMO number holds every word of a query, best first: an id or WMO number that is the query, a name
 * that starts with it, a name with a word that starts with it, a name that holds it; the stations that report before the ones that have
 * stopped within one of these, then the list's order. A query of fewer than three characters finds none: it would find every
 * station. At most `limit` stations are returned, and `total` is how many there are.
 *
 * @param list - The list, prepared
 * @param query - What was typed
 * @param limit - The most stations to return
 * @returns The count and the best stations
 */
export function searchPrepared(list: PreparedStations, query: string, limit: number): StationMatches {
  const words = fold(query).split(/\s+/).filter(Boolean)
  if (!words.length || fold(query).replace(/\s+/g, '').length < MIN_NAME_LETTERS)
    return { total: 0, stations: [] }
  // the same words as the lists that have no umlauts spell them, where the query has one
  const spelledWords = foldSpelled(query).split(/\s+/).filter(Boolean)
  const whole = words.join(' ')
  const spelledWhole = spelledWords.join(' ')
  const spelledDiffers = spelledWhole !== whole
  // the stations by how well they answer: 8 buckets (a score of 1 to 4, reporting or not), each kept to `limit` places
  const buckets: number[][] = Array.from({ length: 8 }, () => [])
  let total = 0
  const { names, spelled, ids, wmo, reporting } = list
  for (let index = 0; index < names.length; index++) {
    const id = ids[index]!
    const number = wmo[index]!
    // the name as the query is held to it: as it is written, or as a list without umlauts would write it
    let name = names[index]!
    let held = words
    if (!holdsAll(`${name} ${id} ${number}`, words)) {
      const other = spelled[index] ?? name
      if ((spelled[index] === null && !spelledDiffers) || !holdsAll(`${other} ${id} ${number}`, spelledWords))
        continue
      name = other
      held = spelledWords
    }
    total++
    let score: number
    if (held.length === 1 && (id === numberTypedAs(held[0]!) || number === numberTypedAs(held[0]!)))
      score = 3
    else if (name.startsWith(held === words ? whole : spelledWhole))
      score = 2
    else if (name.split(/[\s(/-]+/).some(part => part.startsWith(held[0]!)))
      score = 1
    else
      score = 0
    const bucket = buckets[score * 2 + (reporting[index] ? 1 : 0)]!
    if (bucket.length < limit)
      bucket.push(index)
  }
  const { columns } = list
  const stations: StationMatch[] = []
  for (let at = buckets.length - 1; at >= 0 && stations.length < limit; at--) {
    for (const index of buckets[at]!) {
      if (stations.length >= limit)
        break
      stations.push({
        station_id: columns.station_id[index]!,
        name: columns.name[index]!,
        latitude: columns.latitude[index]!,
        longitude: columns.longitude[index]!,
        wmo_id: columns.wmo_id[index]!,
        first_year: columns.first_year[index]!,
        last_year: columns.last_year[index]!,
        reporting: reporting[index]!,
      })
    }
  }
  return { total, stations }
}

/** What a station of the answer of the search is called in the lists the map reads: its network, which the search's groups and the map's `layer` are named by */
export type SearchNetwork = 'forecast' | 'measured' | 'ghcn'

/** The networks the search matches, in the order of its groups */
export const SEARCH_NETWORKS: SearchNetwork[] = ['forecast', 'measured', 'ghcn']

/** The answer of `GET /_search/stations`: for each network that was read, the best stations and how many there are; the networks whose list was not there (`pending`: still being read, `failed`: could not be) */
export interface StationSearchAnswer {
  query: string
  networks: Array<{ network: SearchNetwork, total: number, stations: StationMatch[] }>
  pending: SearchNetwork[]
  failed: SearchNetwork[]
}

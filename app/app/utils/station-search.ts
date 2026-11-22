import type { GhcnStationColumns } from '#shared/types/ghcn-stations'
import { fold } from './palette'

// The stations the search of the header finds by name or number (GH-3790): the matching of a query against a list of stations that
// the app's server keeps as columns (`server/utils/stationSearch.ts`), apart from the server so that a test can hold it. The rule is
// the search's own (`fold`: case and accents aside, every word of the query in the name or the id, in any order), and the map's
// (`searchStations`, which reads its stations through the same `matchStations`): the names that start with the query come first.

/**
 * What the matching reads of a list of stations: the columns of the lists that the app's server keeps (`GhcnStationColumns`) are one, and the
 * map's panel makes the same of the stations it lists (`fieldsOfStations`), so that the header and the map find the same stations.
 */
export interface StationFields {
  name: Array<string | null>
  /** The ids of the lists the search matches are upper-case ASCII (`GM000010147`, `K1234`, `01975`): a query word is compared as upper case */
  station_id: string[]
  wmo_id: Array<string | null>
  last_year: Array<number | null>
}

/**
 * A list of stations made ready to be searched: the names folded once (133k names are not to be folded at every keystroke). The ids and WMO
 * numbers are read from the columns as they are, and whether a station reports from its last year, so that the index holds nothing but the
 * names, and, for the few names that have an umlaut, the other spelling.
 */
export interface PreparedStations<C extends StationFields = GhcnStationColumns> {
  columns: C
  /** Each station's name, folded */
  names: string[]
  /** Each station's name as the lists that have no umlauts write it (`Müller` is `MUELLER`), folded: only of the names that an umlaut makes differ */
  spelled: Map<number, string>
  /** Whether a station with this last year still reports, as the list's rule says */
  reports: (lastYear: number | null) => boolean
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
 * Folds a list of stations once, for {@link matchStations} to compare a query with.
 *
 * @param columns - The list, as the server keeps it
 * @param reports - Whether a station reports: the rule of its list, by its last year
 * @returns The list ready to be searched; it must not change after it
 */
export function prepareStations<C extends StationFields>(columns: C, reports: (lastYear: number | null) => boolean): PreparedStations<C> {
  const spelled = new Map<number, string>()
  const names = columns.name.map((name, index) => {
    const text = name ?? ''
    const plain = fold(text)
    // only a name with an umlaut can be written another way
    if (/[äöüß]/i.test(text))
      spelled.set(index, foldSpelled(text))
    return plain
  })
  return { columns, names, spelled, reports }
}

/** Whether a station holds every word, in its name, its id or its WMO number: no text is made of the three for the purpose */
function holdsAll(name: string, id: string, number: string, words: string[], idWords: string[]): boolean {
  for (let at = 0; at < words.length; at++) {
    if (!name.includes(words[at]!) && !id.includes(idWords[at]!) && !number.includes(words[at]!))
      return false
  }
  return true
}

/** The number of a station as it is written in the lists: the WMO number of `1001` is `01001` */
function numberTypedAs(word: string): string {
  return /^\d{1,5}$/.test(word) ? word.padStart(5, '0') : word
}

/** The stations of a list that answer a query, as their places in it: how many there are in all, and the best `limit` of them */
export interface MatchedIndexes {
  total: number
  indexes: number[]
}

/**
 * The stations of a list whose name, id or WMO number holds every word of a query, best first: an id or WMO number that is the query, a name
 * that starts with it, a name with a word that starts with it, a name that holds it; the stations that report before the ones that have
 * stopped within one of these, then the list's order. A name is held to the query as it is written, and as a list without umlauts would write
 * it. A query of fewer than `minLetters` characters finds none: it would find every station. At most `limit` stations are returned, and `total`
 * is how many there are. The header's search and the map's panel both read their stations through this, so that they find the same ones.
 *
 * @param list - The list, prepared
 * @param query - What was typed
 * @param limit - The most stations to return
 * @param minLetters - The fewest characters of a query that is searched
 * @returns The count and the places of the best stations
 */
export function matchStations(list: PreparedStations<StationFields>, query: string, limit: number, minLetters = MIN_NAME_LETTERS): MatchedIndexes {
  const folded = fold(query)
  const words = folded.split(/\s+/).filter(Boolean)
  if (!words.length || folded.replace(/\s+/g, '').length < minLetters)
    return { total: 0, indexes: [] }
  // the same words as the lists that have no umlauts spell them, where the query has one
  const spelledWords = foldSpelled(query).split(/\s+/).filter(Boolean)
  const whole = words.join(' ')
  const spelledWhole = spelledWords.join(' ')
  const spelledDiffers = spelledWhole !== whole
  // the ids are upper case, the names and numbers are compared as they are folded
  const idWords = words.map(word => word.toUpperCase())
  const spelledIdWords = spelledWords.map(word => word.toUpperCase())
  const wanted = words.length === 1 ? numberTypedAs(words[0]!) : null
  const wantedId = words.length === 1 ? idWords[0]! : null
  const wantedSpelled = spelledWords.length === 1 ? numberTypedAs(spelledWords[0]!) : null
  const wantedSpelledId = spelledWords.length === 1 ? spelledIdWords[0]! : null
  // the stations by how well they answer: 8 buckets (a score of 1 to 4, reporting or not), each kept to `limit` places
  const buckets: number[][] = Array.from({ length: 8 }, () => [])
  let total = 0
  const { names, spelled, reports, columns } = list
  const ids = columns.station_id
  const numbers = columns.wmo_id
  for (let index = 0; index < names.length; index++) {
    const id = ids[index]!
    const number = numbers[index] ?? ''
    // the name as the query is held to it: as it is written, or as a list without umlauts would write it
    let name = names[index]!
    let held = words
    let heldWhole = whole
    let numberWanted = wanted
    let idWanted = wantedId
    if (!holdsAll(name, id, number, words, idWords)) {
      const other = spelled.get(index)
      if (other === undefined && !spelledDiffers)
        continue
      const alt = other ?? name
      if (!holdsAll(alt, id, number, spelledWords, spelledIdWords))
        continue
      name = alt
      held = spelledWords
      heldWhole = spelledWhole
      numberWanted = wantedSpelled
      idWanted = wantedSpelledId
    }
    total++
    let score: number
    if (numberWanted !== null && (id === numberWanted || number === numberWanted || id === idWanted))
      score = 3
    else if (name.startsWith(heldWhole))
      score = 2
    else if (name.split(/[\s(/-]+/).some(part => part.startsWith(held[0]!)))
      score = 1
    else
      score = 0
    const bucket = buckets[score * 2 + (reports(columns.last_year[index] ?? null) ? 1 : 0)]!
    if (bucket.length < limit)
      bucket.push(index)
  }
  const indexes: number[] = []
  for (let at = buckets.length - 1; at >= 0 && indexes.length < limit; at--) {
    for (const index of buckets[at]!) {
      if (indexes.length >= limit)
        break
      indexes.push(index)
    }
  }
  return { total, indexes }
}

/**
 * {@link matchStations} for the lists the server keeps: the best stations with what the search shows of each.
 *
 * @param list - The list, prepared
 * @param query - What was typed
 * @param limit - The most stations to return
 * @returns The count and the best stations
 */
export function searchPrepared(list: PreparedStations<GhcnStationColumns>, query: string, limit: number): StationMatches {
  const { total, indexes } = matchStations(list, query, limit)
  const { columns, reports } = list
  return {
    total,
    stations: indexes.map(index => ({
      station_id: columns.station_id[index]!,
      name: columns.name[index]!,
      latitude: columns.latitude[index]!,
      longitude: columns.longitude[index]!,
      wmo_id: columns.wmo_id[index]!,
      first_year: columns.first_year[index]!,
      last_year: columns.last_year[index]!,
      reporting: reports(columns.last_year[index] ?? null),
    })),
  }
}

/**
 * Whether a station reports by the year of its last value: none, or this year's or last year's, which is the rule of the map's GHCN layer
 * (`ghcnReportingRule`) and which the lists of the search, that have years and no clock, are given.
 */
export function reportsThisOrLastYear(now: () => number = Date.now): (lastYear: number | null) => boolean {
  return (lastYear) => {
    const threshold = new Date(now()).getUTCFullYear() - 1
    return lastYear === null || lastYear >= threshold
  }
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

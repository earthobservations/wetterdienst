// What the app's search (`components/CommandPalette.vue`, GH-3518) finds for what was typed: a text matches when it
// holds every word of the query, in any order, regardless of case and accents ("munchen" finds "München").

/** The text as the search compares it: lower case, without accents, runs of space as one */
export function normalizeForSearch(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().replace(/\s+/g, ' ').trim()
}

/** The words of a query, normalized; none for a query of nothing but space */
export function queryWords(query: string): string[] {
  const normalized = normalizeForSearch(query)
  return normalized ? normalized.split(' ') : []
}

/** Whether every word of the query is in one of the texts; an empty query matches everything */
export function matchesQuery(words: string[], ...texts: (string | null | undefined)[]): boolean {
  if (!words.length)
    return true
  const haystack = normalizeForSearch(texts.filter(Boolean).join(' '))
  return words.every(word => haystack.includes(word))
}

/** The fewest characters a query has before the stations are searched: one letter matches thousands of them */
export const STATION_QUERY_MIN = 2
/** The most stations the search lists: more is a list to scroll through, not an answer */
export const STATION_RESULTS_MAX = 8

interface NamedStation { station_id: string, name: string | null, region: string | null }

/**
 * The stations a query finds, at most {@link STATION_RESULTS_MAX}: a station whose id is the query comes first, then
 * those whose name starts with it, then the rest in the order of the list.
 */
export function findStations<T extends NamedStation>(stations: readonly T[], query: string): T[] {
  const words = queryWords(query)
  if (words.join(' ').length < STATION_QUERY_MIN)
    return []
  const whole = words.join(' ')
  const rank = (station: T) => {
    if (normalizeForSearch(station.station_id) === whole)
      return 0
    return normalizeForSearch(station.name ?? '').startsWith(whole) ? 1 : 2
  }
  return stations
    .filter(station => matchesQuery(words, station.name, station.station_id, station.region))
    .map((station, index) => ({ station, index, rank: rank(station) }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .slice(0, STATION_RESULTS_MAX)
    .map(entry => entry.station)
}

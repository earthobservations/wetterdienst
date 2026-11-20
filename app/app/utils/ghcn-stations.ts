import type { GhcnStationColumns } from '#shared/types/ghcn-stations'
import type { PlacedStation } from './map-tool'

/** Where the app's own server has the list of the stations of NOAA GHCN daily, as columns (`server/routes/_ghcn/map-stations.get.ts`, GH-4267) */
export const GHCN_STATIONS_ROUTE = '/_ghcn/map-stations'

/**
 * The stations of the columns the server hands out: 133k objects of the few fields the map reads, in the list's order. The years
 * are the timestamps the rest of the map reads them from (`yearOf`, `ghcnReportingRule`): the first day of the first year and the
 * last of the last, one string for each year and not one for each station. A station with no last year has no end, which says it reports.
 *
 * @param columns - The answer of the route
 * @returns The stations
 * @throws Error where a column is not as long as the list says, which an answer of another form would be
 */
export function stationsOfColumns(columns: GhcnStationColumns): PlacedStation[] {
  const { count, station_id: ids, latitude, longitude, first_year: first, last_year: last, name, wmo_id: wmo } = columns
  if (![ids, latitude, longitude, first, last, name, wmo].every(column => Array.isArray(column) && column.length === count))
    throw new Error('The list of the stations of NOAA GHCN daily has columns of unequal length.')
  const starts = new Map<number, string>()
  const ends = new Map<number, string>()
  const stamp = (years: Map<number, string>, year: number, rest: string) => {
    let text = years.get(year)
    if (!text) {
      text = `${String(year).padStart(4, '0')}${rest}`
      years.set(year, text)
    }
    return text
  }
  const stations: PlacedStation[] = Array.from({ length: count })
  for (let index = 0; index < count; index++) {
    const from = first[index]!
    const to = last[index]!
    stations[index] = {
      station_id: ids[index]!,
      name: name[index]!,
      region: null,
      latitude: latitude[index]!,
      longitude: longitude[index]!,
      elevation: null,
      wmo_id: wmo[index]!,
      start_timestamp: from === null ? null : stamp(starts, from, '-01-01T00:00:00+00:00'),
      end_timestamp: to === null ? null : stamp(ends, to, '-12-31T00:00:00+00:00'),
    }
  }
  return stations
}

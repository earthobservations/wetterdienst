import type { StationIdsStation } from '#shared/types/api'
import type { MapLayer } from './map-tool'
import type { PaletteItem } from './palette'
import type { SearchNetwork, StationMatch } from './station-search'
import { GHCN_NETWORK, mapSearchLink, mapStationLink, measurementsLink } from './map-tool'

// What the search of the header does with a station (GH-3790): the networks whose stations it matches by name, what a result of each
// leads to, and the ids it asks every network for. Pure, so that a test can hold it; the component (AppCommandPalette.vue) draws it.

/** What the search knows of each network it matches by name: the map's layer it leads to, and how it is named */
export interface StationNetworkInfo {
  /** The group's id in the search */
  group: string
  layer: MapLayer
  /** The provider's name as the search shows it */
  provider: string
}

export const STATION_NETWORKS: Record<SearchNetwork, StationNetworkInfo> = {
  forecast: { group: 'stations-forecast', layer: 'forecast', provider: 'DWD' },
  measured: { group: 'stations-measured', layer: 'measured', provider: 'DWD' },
  ghcn: { group: 'stations-ghcn', layer: 'ghcn', provider: 'NOAA' },
}

/** The words the lines of a station are made of, from the catalogs: what a station found by name says about itself */
export interface StationWords {
  /** The network as the lines name it: `MOSMIX forecast`, `measurements`, `GHCN daily` */
  network: (network: SearchNetwork) => string
  /** `ended 1997` */
  ended: (year: number) => string
}

/**
 * The line under a result: the provider, the network, the id the network numbers the station by and, where it has stopped
 * reporting, the year its record ended in.
 */
export function stationLine(network: SearchNetwork, match: StationMatch, words: StationWords): string {
  const info = STATION_NETWORKS[network]
  return [info.provider, words.network(network), match.station_id, !match.reporting && match.last_year !== null ? words.ended(match.last_year) : null]
    .filter(Boolean)
    .join(' · ')
}

/** A station found by name as an item of the search: it leads to the map with the station picked, on the layer of its network */
export function itemOfStation(network: SearchNetwork, match: StationMatch, words: StationWords, icon: string): PaletteItem {
  const info = STATION_NETWORKS[network]
  return {
    id: `station-${network}-${match.station_id}`,
    label: match.name ?? match.station_id,
    description: stationLine(network, match, words),
    icon,
    to: mapStationLink(info.layer, match.station_id),
  }
}

/** The last item of a network's stations where there are more than are shown: the map's own search of the layer, started on the query */
export function moreStationsLink(network: SearchNetwork, query: string): string {
  return mapSearchLink(STATION_NETWORKS[network].layer, query)
}

// ---- the ids ---------------------------------------------------------------------------------------------------

/** What an id typed in is: a WMO number, a WIGOS identifier or an ICAO code, with the name of the parameter `GET /api/station-ids` takes it as */
export interface TypedStationId {
  kind: 'wmo' | 'wigos' | 'icao'
  /** As it is asked for: an ICAO code in capitals, the others as they were typed */
  id: string
  /** The query parameter of `station-ids` */
  param: 'wmo_id' | 'wigos_id' | 'icao_id'
}

/**
 * Whether what is typed is the id of a station in WMO's or ICAO's schemes (GH-4286): a WMO number is five digits (`10381`), a WIGOS
 * identifier four parts with the WIGOS prefix (`0-20000-0-10381`, `0-276-3-…`), an ICAO code four letters (`EDDH`; a name of four
 * letters, `Kiel`, is one too: the search of all networks is offered, never run on its own). Null for anything else.
 */
export function parseStationId(text: string): TypedStationId | null {
  const typed = text.trim()
  if (/^\d{5}$/.test(typed))
    return { kind: 'wmo', id: typed, param: 'wmo_id' }
  if (/^0-\d{1,6}-\d{1,5}-[\w.-]{1,16}$/.test(typed))
    return { kind: 'wigos', id: typed, param: 'wigos_id' }
  if (/^[a-z]{4}$/i.test(typed))
    return { kind: 'icao', id: typed.toUpperCase(), param: 'icao_id' }
  return null
}

/** Where a station that `station-ids` found leads: the map where it shows the station's network (the forecast's points, DWD's measurements, NOAA GHCN daily), else the Explorer, with the network and the station chosen */
export function stationIdLink(row: Pick<StationIdsStation, 'provider' | 'network' | 'resolution' | 'dataset' | 'station_id'>): { to: string, map: boolean } {
  if (row.provider === 'dwd' && row.network === 'mosmix')
    return { to: mapStationLink('forecast', row.station_id), map: true }
  if (row.provider === 'dwd' && row.network === 'observation')
    return { to: mapStationLink('measured', row.station_id, { resolution: row.resolution, dataset: row.dataset }), map: true }
  if (row.provider === GHCN_NETWORK.provider && row.network === GHCN_NETWORK.network)
    return { to: mapStationLink('ghcn', row.station_id), map: true }
  return { to: measurementsLink({ resolution: row.resolution, dataset: row.dataset }, row.station_id, { provider: row.provider, network: row.network }), map: false }
}

/** The provider's name as the search shows it (`DWD`), the networks of the lists it matches by name as it names them there (`MOSMIX forecast`), and the words of a lead to the Explorer (`opens the Explorer`) */
export interface IdRowWords {
  provider: string
  network: (network: SearchNetwork) => string
  opensExplorer: string
}

/** The network of the lists the search matches by name that a station of the id search is of (the forecast's points, DWD's measuring stations, NOAA GHCN daily), or null for any other */
function searchNetworkOf(row: Pick<StationIdsStation, 'provider' | 'network'>): SearchNetwork | null {
  if (row.provider === 'dwd' && row.network === 'mosmix')
    return 'forecast'
  if (row.provider === 'dwd' && row.network === 'observation')
    return 'measured'
  return row.provider === GHCN_NETWORK.provider && row.network === GHCN_NETWORK.network ? 'ghcn' : null
}

/** The icon of a station that leads to the map and of one that leads to the Explorer */
export interface IdRowIcons {
  map: string
  explorer: string
}

/**
 * A station that `station-ids` found as an item of the search: its name, then the provider, the network (named as the groups of the stations found by name
 * name it where it is one of those, else as the backend does), the id the network numbers it by and, where there is no map of its network, that it opens the Explorer (`opensExplorer`, in the reader's language), which it does with
 * the network and the station chosen.
 *
 * @param row - The station
 * @param words - The provider's name as the search shows it, and the words of an Explorer lead
 * @param icons - The icon of a station that leads to the map and of one that leads to the Explorer
 * @returns The item
 */
export function itemOfIdRow(row: StationIdsStation, words: IdRowWords, icons: IdRowIcons): PaletteItem {
  const link = stationIdLink(row)
  const known = searchNetworkOf(row)
  return {
    id: `station-id-${row.provider}-${row.network}-${row.resolution}-${row.dataset}-${row.station_id}`,
    label: row.name ?? row.station_id,
    description: [words.provider, known ? words.network(known) : row.network, row.station_id, link.map ? null : words.opensExplorer].filter(Boolean).join(' · '),
    icon: link.map ? icons.map : icons.explorer,
    to: link.to,
  }
}

/** The stations of an answer of `station-ids` in the order the search lists them: the ones that carry the id asked for before the ones that carry an equivalent id, each in the backend's order */
export function sortedIdRows<T extends Pick<StationIdsStation, 'match'>>(rows: T[]): T[] {
  return [...rows.keys()]
    .sort((a, b) => Number(rows[a]!.match !== 'direct') - Number(rows[b]!.match !== 'direct') || a - b)
    .map(index => rows[index]!)
}

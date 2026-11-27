import { DateTime } from 'luxon'

/**
 * What the backend answers for DWD's UV index and pollen forecasts (GH-4501), as the tests of the "UV & pollen" panel serve it:
 * the shapes of `_Station` and `_ValuesItemDict` in the OpenAPI snapshot. The 27 regions are those of `dwd/pollen`
 * (`src/wetterdienst/provider/dwd/pollen/regions.py`: the id DWD numbers the area with, the name `<region>: <part-region>` and the
 * `region` column), which is why they are written out and not made up.
 */

export const POLLEN_REGION_STATIONS = [
  { station_id: '11', name: 'Schleswig-Holstein und Hamburg: Inseln und Marschen', region: 'Schleswig-Holstein und Hamburg' },
  { station_id: '12', name: 'Schleswig-Holstein und Hamburg: Geest,Schleswig-Holstein und Hamburg', region: 'Schleswig-Holstein und Hamburg' },
  { station_id: '20', name: 'Mecklenburg-Vorpommern', region: 'Mecklenburg-Vorpommern' },
  { station_id: '31', name: 'Niedersachsen und Bremen: Westl. Niedersachsen/Bremen', region: 'Niedersachsen und Bremen' },
  { station_id: '32', name: 'Niedersachsen und Bremen: Östl. Niedersachsen', region: 'Niedersachsen und Bremen' },
  { station_id: '41', name: 'Nordrhein-Westfalen: Rhein.-Westfäl. Tiefland', region: 'Nordrhein-Westfalen' },
  { station_id: '42', name: 'Nordrhein-Westfalen: Ostwestfalen', region: 'Nordrhein-Westfalen' },
  { station_id: '43', name: 'Nordrhein-Westfalen: Mittelgebirge NRW', region: 'Nordrhein-Westfalen' },
  { station_id: '50', name: 'Brandenburg und Berlin', region: 'Brandenburg und Berlin' },
  { station_id: '61', name: 'Sachsen-Anhalt: Tiefland Sachsen-Anhalt', region: 'Sachsen-Anhalt' },
  { station_id: '62', name: 'Sachsen-Anhalt: Harz', region: 'Sachsen-Anhalt' },
  { station_id: '71', name: 'Thüringen: Tiefland Thüringen', region: 'Thüringen' },
  { station_id: '72', name: 'Thüringen: Mittelgebirge Thüringen', region: 'Thüringen' },
  { station_id: '81', name: 'Sachsen: Tiefland Sachsen', region: 'Sachsen' },
  { station_id: '82', name: 'Sachsen: Mittelgebirge Sachsen', region: 'Sachsen' },
  { station_id: '91', name: 'Hessen: Nordhessen und hess. Mittelgebirge', region: 'Hessen' },
  { station_id: '92', name: 'Hessen: Rhein-Main', region: 'Hessen' },
  { station_id: '101', name: 'Rheinland-Pfalz und Saarland: Rhein, Pfalz, Nahe und Mosel', region: 'Rheinland-Pfalz und Saarland' },
  { station_id: '102', name: 'Rheinland-Pfalz und Saarland: Mittelgebirgsbereich Rheinland-Pfalz', region: 'Rheinland-Pfalz und Saarland' },
  { station_id: '103', name: 'Rheinland-Pfalz und Saarland: Saarland', region: 'Rheinland-Pfalz und Saarland' },
  { station_id: '111', name: 'Baden-Württemberg: Oberrhein und unteres Neckartal', region: 'Baden-Württemberg' },
  { station_id: '112', name: 'Baden-Württemberg: Hohenlohe/mittlerer Neckar/Oberschwaben', region: 'Baden-Württemberg' },
  { station_id: '113', name: 'Baden-Württemberg: Mittelgebirge Baden-Württemberg', region: 'Baden-Württemberg' },
  { station_id: '121', name: 'Bayern: Allgäu/Oberbayern/Bay. Wald', region: 'Bayern' },
  { station_id: '122', name: 'Bayern: Donauniederungen', region: 'Bayern' },
  { station_id: '123', name: 'Bayern: Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken', region: 'Bayern' },
  { station_id: '124', name: 'Bayern: Mainfranken', region: 'Bayern' },
]

/** The stations of the answers, whole: a station of `dwd/pollen` has no position, which the answer writes as null */
export const POLLEN_STATIONS_ANSWER = POLLEN_REGION_STATIONS.map(region => ({
  resolution: 'daily',
  dataset: 'data',
  ...region,
  start_timestamp: null,
  end_timestamp: null,
  latitude: null,
  longitude: null,
  elevation: null,
  wmo_id: null,
  wigos_id: null,
  icao_id: null,
}))

/** A place of the UV index, as `dwd/uvi` lists it (`places.py`) */
export function uvPlace(station_id: string, name: string, latitude: number, longitude: number) {
  return { resolution: 'daily', dataset: 'data', station_id, name, latitude, longitude, elevation: 100, region: null, wmo_id: null, wigos_id: null, icao_id: null, start_timestamp: null, end_timestamp: null }
}

export const UV_DRESDEN = uvPlace('dresden', 'Dresden', 51.1278, 13.7543)
export const UV_BERLIN = uvPlace('berlin', 'Berlin', 52.4676, 13.402)

/** A station of `dwd/observation` with the state it is in, as the list of any of its datasets gives it */
export function observationStation(station_id: string, name: string, region: string, latitude: number, longitude: number) {
  return { resolution: 'daily', dataset: 'climate_summary', station_id, name, region, latitude, longitude, elevation: 100, wmo_id: null, wigos_id: null, icao_id: null, start_timestamp: null, end_timestamp: null }
}

export const OBSERVATION_DRESDEN = observationStation('01048', 'Dresden-Klotzsche', 'Sachsen', 51.1278, 13.7543)

/** A MOSMIX station, as `/api/stations` lists it, with the fields the page reads */
export const MOSMIX_DRESDEN = { station_id: '10488', name: 'DRESDEN-KLOTZSCHE', latitude: 51.13, longitude: 13.75, elevation: 227 }
export const MOSMIX_AMSTERDAM = { station_id: '06240', name: 'AMSTERDAM SCHIPHOL', latitude: 52.3, longitude: 4.77, elevation: -3 }
/** Stations of other countries that the box of DWD's warnings holds, a few kilometres from German stations and places */
export const MOSMIX_STRASBOURG = { station_id: '07190', name: 'STRASBOURG-ENTZHEIM', latitude: 48.55, longitude: 7.63, elevation: 150 }
export const MOSMIX_SALZBURG = { station_id: '11150', name: 'SALZBURG-FLUGHAFEN', latitude: 47.8, longitude: 13.0, elevation: 430 }
export const MOSMIX_BASEL = { station_id: '06601', name: 'BASEL-BINNINGEN', latitude: 47.54, longitude: 7.58, elevation: 316 }
export const MOSMIX_VENLO = { station_id: '06391', name: 'ARCEN', latitude: 51.5, longitude: 6.2, elevation: 20 }
export const MOSMIX_PARIS = { station_id: '07149', name: 'PARIS-ORLY', latitude: 48.72, longitude: 2.4, elevation: 90 }

/** The German calendar date it is `offset` days from today, which is what the panel's Today is for a station in Germany */
export function germanDay(offset = 0, now: number = Date.now()): string {
  return DateTime.fromMillis(now).setZone('Europe/Berlin').plus({ days: offset }).toISODate()!
}

/** The timestamp of a day in a daily answer: its date at 00:00 UTC */
export const stampOf = (day: string) => `${day}T00:00:00+00:00`

/** The UV index of a place for the days from `from` (default today): one row each, in whole numbers */
export function uvValues(stationId: string, indices: (number | null)[], from = 0, now: number = Date.now()) {
  return indices.map((value, index) => ({
    station_id: stationId,
    resolution: 'daily',
    dataset: 'data',
    parameter: 'uv_index_max',
    timestamp: stampOf(germanDay(from + index, now)),
    value,
    quality_flags: null,
  }))
}

export const POLLEN_PARAMETERS = ['hazel', 'alder', 'ash', 'birch', 'grass', 'rye', 'mugwort', 'ragweed'] as const

/** The levels of the pollen types for the days of a forecast, by type */
export type PollenLevels = Partial<Record<typeof POLLEN_PARAMETERS[number], readonly (number | null)[]>>

/**
 * The pollen load of regions for three days: `levels` gives the levels of each type for each day, by type, for every region asked
 * for (`byRegion` overrides one's); a type it does not name is 0
 */
export function pollenValues(
  regionIds: string[],
  levels: PollenLevels,
  byRegion: Record<string, PollenLevels> = {},
  from = 0,
  now: number = Date.now(),
) {
  return regionIds.flatMap(id => POLLEN_PARAMETERS.flatMap((type) => {
    const days = (byRegion[id] ?? levels)[type] ?? [0, 0, 0]
    return days.map((value, index) => ({
      station_id: id,
      resolution: 'daily',
      dataset: 'data',
      parameter: `pollen_load_${type}`,
      timestamp: stampOf(germanDay(from + index, now)),
      value,
      quality_flags: null,
    }))
  }))
}

/** A season of pollen at the start of a spring: hazel and alder are in bloom, ash and birch are about to be */
export const SPRING_LEVELS = {
  hazel: [2, 2.5, 3],
  alder: [1, 1.5, 2],
  ash: [0, 0.5, 0.5],
  birch: [0, 0, 0.5],
  grass: [0, 0, 0],
  rye: [0, 0, 0],
  mugwort: [0, 0, 0],
  ragweed: [0, 0, 0],
} as const

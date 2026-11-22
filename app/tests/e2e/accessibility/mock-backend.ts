import type { Page, Route } from '@playwright/test'
import type { StationSearchAnswer } from '../../../app/utils/station-search'
import type {
  GlossaryEntry,
  HistoryResponse,
  ProviderNetworkCoverageResponse,
  ProvidersResponse,
  Station,
  UnitType,
  Value,
} from '../../../shared/types/api'
import type { StripesFixture } from '../../helpers/stripes-backend'
import { Buffer } from 'node:buffer'
import { prepareStations, searchPrepared } from '../../../app/utils/station-search'
import { radarAnswer } from '../../helpers/radar-answer'
import { radarPng } from '../../helpers/radar-image'
import { emptyScan } from '../../helpers/storm-cells-answer'
import { stripesAnswer } from '../../helpers/stripes-answer'
import { ghcnAnnualOfFixture, valuesOfFixture } from '../../helpers/stripes-backend'

// What the accessibility spec shows the app instead of a backend.
//
// The spec scans pages in states -- a map with stations, a chart, an error -- that need an answer
// from `/api/*`, and the suite must not ask a real provider for one: the backend answers from DWD
// opendata, which is slow, flaky and changes. Every request the app makes to `/api/*` is
// therefore answered here, in the browser, before it reaches the app's own server or the backend.
// The answers are small and fixed, shaped as `shared/types/api.ts` has them.
//
// A request that nothing below answers is a request the spec did not plan for. It is answered
// with a 501 and collected, and the spec fails on it rather than scan a page that is waiting for
// an answer that never comes.

export type Handler = (url: URL, route: Route) => unknown | Promise<unknown>

/**
 * The answers by `/api/<path>`, to be replaced one by one where a state needs a different one.
 *
 * Besides the paths of the API, three keys name what the climate stripes are made of (GH-4258): `stripes/stations` and `stripes/values`
 * answer the requests for the annual record (`/api/stations` and `/api/values` of `annual/...` parameters: the stations that have
 * stripes, and a station's years), and `_ghcn/stations` and `_ghcn/annual` the app's own server's routes for GHCN daily. The values
 * are written as the stripes' fixtures are (`{ series, values }`, see `tests/helpers/stripes-backend.ts`) and answered as the API does
 */
export type Handlers = Record<string, Handler>

/** What a handler returns to answer with an error instead of a body; `extra` are the fields of a problem beside `detail` */
export class ApiFailure {
  constructor(readonly status: number, readonly detail: string, readonly extra: Record<string, unknown> = {}) {}
}

/** What a handler returns to answer with a file instead of JSON (a frame of the radar, GH-3788): its bytes and their type */
export class ApiBinary {
  constructor(readonly body: Buffer, readonly contentType: string, readonly headers: Record<string, string> = {}) {}
}

function parameter(name: string, name_original: string, unit_type: UnitType, unit: string, description: string) {
  return { name, name_original, unit_type, unit, description }
}

const OBSERVATION_COVERAGE = {
  hourly: {
    description: null,
    datasets: {
      temperature_air: {
        description: 'Hourly air temperature and relative humidity at 2 m height.',
        parameters: [
          parameter('temperature_air_mean_2m', 'tt_tu', 'temperature', 'degree_celsius', 'Hourly air temperature at 2 m height.'),
          parameter('humidity', 'rf_tu', 'fraction', 'percent', 'Hourly relative humidity.'),
        ],
      },
    },
  },
  daily: {
    description: null,
    datasets: {
      climate_summary: {
        description: 'Daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany.',
        parameters: [
          parameter('temperature_air_max_2m', 'txk', 'temperature', 'degree_celsius', 'Daily maximum of temperature at 2 m height.'),
          parameter('temperature_air_mean_2m', 'tmk', 'temperature', 'degree_celsius', 'Daily mean of temperature at 2 m height.'),
          parameter('temperature_air_min_2m', 'tnk', 'temperature', 'degree_celsius', 'Daily minimum of temperature at 2 m height.'),
          parameter('precipitation_height', 'rsk', 'precipitation', 'millimeter', 'Daily precipitation height.'),
        ],
      },
    },
  },
} satisfies ProviderNetworkCoverageResponse

/**
 * The end of a station that is running, as the REST API gives one: the day of its last value, two days ago, and no
 * `null` (the map tool takes a station with no end for one whose status is not known)
 */
const RUNNING_END = new Date(Date.now() - 2 * 86_400_000).toISOString().replace(/T.*$/, 'T00:00:00+00:00')

/** Daily climate summary of the stations the explorer, the history and the maps are shown with */
export const STATIONS: Station[] = [
  { station_id: '00011', name: 'Donaueschingen (Landeplatz)', region: 'Baden-Württemberg', latitude: 47.9737, longitude: 8.5205, elevation: 680, start_timestamp: '1980-09-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00044', name: 'Großenkneten', region: 'Niedersachsen', latitude: 52.9336, longitude: 8.2370, elevation: 44, start_timestamp: '1971-03-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00071', name: 'Albstadt-Badkap', region: 'Baden-Württemberg', latitude: 48.2156, longitude: 8.9784, elevation: 759, start_timestamp: '1986-11-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00073', name: 'Aldersbach-Kriestorf', region: 'Bayern', latitude: 48.6159, longitude: 13.0506, elevation: 340, start_timestamp: '1964-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00091', name: 'Alfhausen', region: 'Niedersachsen', latitude: 52.4853, longitude: 7.9126, elevation: 65, start_timestamp: '1993-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00096', name: 'Neuhaus am Rennweg', region: 'Thüringen', latitude: 50.5063, longitude: 11.1283, elevation: 840, start_timestamp: '2004-12-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00102', name: 'Leuchtturm Alte Weser', region: 'Niedersachsen', latitude: 53.8633, longitude: 8.1275, elevation: 3, start_timestamp: '1997-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00125', name: 'Andechs-Rothenfeld', region: 'Bayern', latitude: 47.9794, longitude: 11.1888, elevation: 680, start_timestamp: '2004-12-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00131', name: 'Angermünde', region: 'Brandenburg', latitude: 53.0301, longitude: 13.9951, elevation: 54, start_timestamp: '1991-03-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00183', name: 'Arkona', region: 'Mecklenburg-Vorpommern', latitude: 54.6791, longitude: 13.4343, elevation: 42, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00198', name: 'Artern', region: 'Thüringen', latitude: 51.3745, longitude: 11.2915, elevation: 164, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: '2018-12-31T00:00:00+00:00' },
  { station_id: '00205', name: 'Aue', region: 'Sachsen', latitude: 50.5919, longitude: 12.7095, elevation: 450, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
]

const MOSMIX_STATION: Station = {
  station_id: '01001',
  name: 'JAN MAYEN',
  region: null,
  latitude: 70.93,
  longitude: -8.67,
  elevation: 10,
  start_timestamp: null,
  end_timestamp: null,
}

/** The MOSMIX-SNOW stations the mock knows (the real dataset has 15, all in the Bavarian Alps): the stations of `hourly/snow` */
export const SNOW_STATIONS: Station[] = [
  { station_id: 'Z901', name: 'HOERMOOS', region: null, latitude: 47.5, longitude: 12.0, elevation: 1060, start_timestamp: null, end_timestamp: null },
  { station_id: 'Z914', name: 'ZUGSPITZPLATT', region: null, latitude: 47.4, longitude: 11.0, elevation: 2420, start_timestamp: null, end_timestamp: null },
]

const MOSMIX_STATIONS: Station[] = [
  MOSMIX_STATION,
  { station_id: '10147', name: 'HAMBURG-FUHLSBUETTEL', region: null, latitude: 53.63, longitude: 10.0, elevation: 11, start_timestamp: null, end_timestamp: null },
  { station_id: '10384', name: 'BERLIN-TEMPELHOF', region: null, latitude: 52.47, longitude: 13.4, elevation: 49, start_timestamp: null, end_timestamp: null },
  { station_id: '10865', name: 'MUENCHEN-STADT', region: null, latitude: 48.16, longitude: 11.54, elevation: 515, start_timestamp: null, end_timestamp: null },
]

const STRIPES_STATIONS: Station[] = STATIONS.slice(0, 6).map(station => ({
  station_id: station.station_id,
  name: station.name,
  region: station.region,
  latitude: station.latitude,
  longitude: station.longitude,
  elevation: station.elevation,
  start_timestamp: '1950-01-01T00:00:00+00:00',
  // an annual list ends with the last year, as the real one does
  end_timestamp: `${new Date().getUTCFullYear() - 1}-12-31T00:00:00+00:00`,
}))

/**
 * `GET /api/providers`: DWD with a licence, a credit line, two networks with stations and a standalone one, and AEMET with a
 * key (which this server has not) and no terms. The Explorer's selects read it: it offers what is configured
 */
const PROVIDER_LIST: ProvidersResponse = {
  metadata: {
    api_version: '1',
    schema_version: '1',
    retrieved_at: '2026-10-17T10:00:00.000000+00:00',
    counts: { providers: 2, networks: 4, parameters: 24 },
    warnings: [],
  },
  providers: [
    {
      provider: 'dwd',
      name_short: 'DWD',
      name_local: 'Deutscher Wetterdienst',
      name_english: 'German Weather Service',
      country: 'Germany',
      country_code: 'DE',
      license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' },
      attribution: 'Source: Deutscher Wetterdienst',
      networks: [
        {
          network: 'observation',
          kind: 'observation',
          url: 'https://opendata.dwd.de/climate_environment/CDC/',
          copyright: '© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)',
          auth: false,
          configured: true,
          date_required: false,
          parameters: 12,
        },
        {
          network: 'mosmix',
          kind: 'forecast',
          url: 'https://opendata.dwd.de/weather/local_forecasts/mos/',
          copyright: '© Deutscher Wetterdienst (DWD), MOSMIX',
          auth: false,
          configured: true,
          date_required: false,
          parameters: 6,
        },
        {
          network: 'radar',
          kind: 'radar',
          url: 'https://opendata.dwd.de/weather/radar/',
          copyright: '© Deutscher Wetterdienst (DWD), radar products',
          auth: false,
          configured: true,
          date_required: false,
          parameters: 0,
        },
      ],
    },
    {
      provider: 'aemet',
      name_short: 'AEMET',
      name_local: 'Agencia Estatal de Meteorología',
      name_english: 'State Meteorological Agency of Spain',
      country: 'Spain',
      country_code: 'ES',
      license: null,
      attribution: null,
      networks: [
        {
          network: 'observation',
          kind: 'observation',
          url: 'https://opendata.aemet.es/',
          copyright: '© AEMET',
          auth: true,
          configured: false,
          date_required: true,
          parameters: 6,
        },
      ],
    },
  ],
}

const GLOSSARY: GlossaryEntry[] = [
  { name: 'temperature_air_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Mean air temperature at 2 m height.' },
  { name: 'temperature_air_max_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Maximum air temperature at 2 m height.' },
  { name: 'temperature_air_min_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Minimum air temperature at 2 m height.' },
  { name: 'temperature_dew_point_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Dew point temperature at 2 m height.' },
  { name: 'precipitation_height', unit_type: 'precipitation', unit: 'millimeter', unit_symbol: 'mm', description: 'Height of precipitation accumulated over the interval.' },
  { name: 'humidity', unit_type: 'fraction', unit: 'percent', unit_symbol: '%', description: 'Relative humidity of the air.' },
  { name: 'wind_speed', unit_type: 'speed', unit: 'meter_per_second', unit_symbol: 'm/s', description: 'Mean wind speed.' },
  { name: 'wind_direction', unit_type: 'angle', unit: 'degree', unit_symbol: '°', description: 'Direction the wind blows from.' },
  { name: 'pressure_air_site', unit_type: 'pressure', unit: 'hectopascal', unit_symbol: 'hPa', description: 'Air pressure at the height of the station.' },
  { name: 'sunshine_duration', unit_type: 'time', unit: 'hour', unit_symbol: 'h', description: 'Duration of sunshine.' },
  { name: 'cloud_cover_total', unit_type: 'fraction', unit: 'decimal', unit_symbol: '', description: 'Fraction of the sky covered by clouds.' },
  { name: 'visibility_range', unit_type: 'length_medium', unit: 'meter', unit_symbol: 'm', description: 'Distance at which objects can still be seen.' },
]

function isoDay(year: number, month: number, day: number): string {
  return new Date(Date.UTC(year, month - 1, day)).toISOString().replace('.000Z', '+00:00')
}

/** Daily values of station 00011, as `/api/values` answers it in the long shape */
function observationValues(url: URL): Value[] {
  const requested = (url.searchParams.get('parameters') ?? '').split(',').filter(Boolean)
  const names = requested.map(entry => entry.split('/')[2]).filter((name): name is string => Boolean(name))
  const parameters = names.length ? names : ['temperature_air_mean_2m']
  const stations = (url.searchParams.getAll('stations').join(',') || '00011').split(',')
  const values: Value[] = []
  for (const station_id of stations) {
    for (const name of parameters) {
      for (let day = 0; day < 30; day++) {
        // a fixed curve, not a random one: the same page for every scan
        const base = name.includes('max') ? 18 : name.includes('min') ? 6 : name.includes('precipitation') ? 2 : 12
        values.push({
          station_id,
          resolution: 'daily',
          dataset: 'climate_summary',
          parameter: name,
          timestamp: isoDay(2026, 9, day + 1),
          value: Math.round((base + 4 * Math.sin(day / 4)) * 10) / 10,
          quality_flags: null,
        })
      }
    }
  }
  return values
}

/** Three days of hourly MOSMIX values from the hour of `now` on, for each series the meteogram draws */
function forecastValues(url: URL, now: Date): Value[] {
  const station_id = url.searchParams.get('stations') ?? MOSMIX_STATION.station_id
  const start = new Date(now)
  start.setUTCMinutes(0, 0, 0)
  const series: Record<string, (hour: number) => number> = {
    temperature_air_2m: hour => 8 + 5 * Math.sin((hour - 9) / 24 * 2 * Math.PI),
    temperature_dew_point_2m: hour => 4 + 3 * Math.sin((hour - 9) / 24 * 2 * Math.PI),
    precipitation_amount_significant_weather_last_1h: hour => (hour % 11 < 3 ? 0.6 : 0),
    wind_speed: hour => 5 + 2 * Math.sin(hour / 7),
    wind_direction: hour => (220 + hour * 3) % 360,
    wind_gust_max_last_1h: hour => 9 + 3 * Math.sin(hour / 7),
    cloud_cover_total: hour => Math.min(1, Math.max(0, 0.5 + 0.4 * Math.sin(hour / 9))),
    cloud_cover_below_2km: hour => Math.min(1, Math.max(0, 0.3 + 0.3 * Math.sin(hour / 8))),
    cloud_cover_between_2km_and_7km: hour => Math.min(1, Math.max(0, 0.3 + 0.3 * Math.sin(hour / 10))),
    cloud_cover_above_7km: hour => Math.min(1, Math.max(0, 0.2 + 0.2 * Math.sin(hour / 12))),
    pressure_air_sea_level: hour => 1012 + 4 * Math.sin(hour / 20),
  }
  const values: Value[] = []
  for (const [parameterName, curve] of Object.entries(series)) {
    for (let hour = 0; hour < 72; hour++) {
      values.push({
        station_id,
        resolution: 'hourly',
        dataset: 'large',
        parameter: parameterName,
        timestamp: new Date(start.getTime() + hour * 3_600_000).toISOString().replace('.000Z', '+00:00'),
        value: Math.round(curve(hour) * 100) / 100,
        quality_flags: null,
      })
    }
  }
  return values
}

/** Whether a request of `/api/values` is for the snow forecast (the dataset `hourly/snow`, MOSMIX-SNOW) */
export function isSnowRequest(url: URL): boolean {
  return (url.searchParams.get('parameters') ?? '').split(',').some(entry => entry.startsWith('hourly/snow/'))
}

/**
 * The snow forecast of a station, as `/api/values` answers it for `hourly/snow`: DWD's MOSMIX-SNOW has the new snow of the 3
 * hours before, the snow depth and the chance of more than 10 cm of new snow within 24 hours at the 00, 03, ..., 21 UTC steps,
 * and, for some stations, a value at hours between the steps. Those are wrong on purpose here (a new snow of 40 cm in an
 * hour): a panel that draws them shows it. Snow falls for 18 hours from the 10th. Three days, like the forecast it joins.
 */
function snowValues(url: URL, now: Date): Record<string, unknown> {
  const station_id = url.searchParams.get('stations') ?? 'Z914'
  const start = new Date(now)
  start.setUTCMinutes(0, 0, 0)
  const values: Value[] = []
  let depth = 140
  for (let hour = 0; hour < 72; hour++) {
    const time = new Date(start.getTime() + hour * 3_600_000)
    const step = time.getUTCHours() % 3 === 0
    const falling = hour >= 10 && hour < 28
    const fresh = falling ? Math.round((0.6 + 4.8 * Math.sin((hour - 10) / 18 * Math.PI)) * 10) / 10 : 0
    if (step)
      depth += fresh
    const stamp = time.toISOString().replace('.000Z', '+00:00')
    const at = (parameter: string, value: number) => values.push({ station_id, resolution: 'hourly', dataset: 'snow', parameter, timestamp: stamp, value, quality_flags: null })
    at('snow_depth_new_last_3h', step ? fresh : 40)
    at('snow_depth', step ? Math.round(depth * 10) / 10 : 400)
    at('probability_snow_depth_new_gt_10cm_last_24h', step ? Math.round(Math.min(85, Math.max(0, (hour - 4) * 6, 0)) * (hour > 48 ? 0.3 : 1)) : 99)
  }
  return {
    values,
    metadata: {
      parameters: [
        { name: 'snow_depth_new_last_3h', unit: 'cm' },
        { name: 'snow_depth', unit: 'cm' },
        { name: 'probability_snow_depth_new_gt_10cm_last_24h', unit: '%' },
      ],
    },
  }
}

/** The stations of GHCN daily that report and have a record long enough: Hamburg and New York */
const GHCN_STRIPES_STATIONS: Station[] = [
  { station_id: 'GM000010147', name: 'HAMBURG FUHLSBUETTEL', region: null, latitude: 53.635, longitude: 9.99, elevation: 11, wmo_id: '10147', start_timestamp: '1891-01-01T00:00:00.000000+00:00', end_timestamp: null },
  { station_id: 'USW00094728', name: 'NEW YORK CNTRL PK TWR', region: null, latitude: 40.7789, longitude: -73.9692, elevation: 42.7, start_timestamp: '1869-01-01T00:00:00.000000+00:00', end_timestamp: null },
]

// ---- the search of the header (GH-3790) ---------------------------------------------------------------------------

/** The columns of a list of stations, as the app's server keeps them for the search (`server/utils/stationSearch.ts`) */
function searchColumns(stations: Station[]) {
  const year = (timestamp: string | null | undefined) => (timestamp ? Number(timestamp.slice(0, 4)) : null)
  return {
    count: stations.length,
    retrieved_at: null,
    station_id: stations.map(station => station.station_id),
    latitude: stations.map(station => station.latitude as number),
    longitude: stations.map(station => station.longitude as number),
    first_year: stations.map(station => year(station.start_timestamp)),
    last_year: stations.map(station => year(station.end_timestamp)),
    name: stations.map(station => station.name ?? null),
    wmo_id: stations.map(station => station.wmo_id ?? null),
  }
}

const THIS_YEAR = new Date().getUTCFullYear()
/** A station reports with no end or an end last year or this, as the map's GHCN layer reads a record */
const reportsIn = (lastYear: number | null) => lastYear === null || lastYear >= THIS_YEAR - 1

/** DWD's measuring stations of the search: the ones of the lists, and Hamburg's, which a search for the town finds in all three networks */
const SEARCH_MEASURED: Station[] = [
  ...STATIONS,
  { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', region: 'Hamburg', latitude: 53.6332, longitude: 9.9881, elevation: 11, wmo_id: '10147', start_timestamp: '1891-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '02597', name: 'Hamburg-Billwerder', region: 'Hamburg', latitude: 53.5, longitude: 10.1, elevation: 4, start_timestamp: '1951-01-01T00:00:00+00:00', end_timestamp: '1997-12-31T00:00:00+00:00' },
  { station_id: '01981', name: 'Hamburg-Neuwiedenthal', region: 'Hamburg', latitude: 53.47, longitude: 9.9, elevation: 5, start_timestamp: '1979-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
]
const SEARCH_GHCN: Station[] = [
  ...GHCN_STRIPES_STATIONS,
  ...['HAMBURG', 'HAMBURG 2', 'HAMBURG 3 NE', 'HAMBURG 5 SSE', 'HAMBURG AIRPORT', 'HAMBURG-FINKENWERDER'].map((name, index) => ({ station_id: `USC00${30000 + index}`, name, region: null, latitude: 42.7 + index / 10, longitude: -78.8, elevation: 200, wmo_id: null, start_timestamp: '1950-01-01T00:00:00.000000+00:00', end_timestamp: index % 2 ? '1990-12-31T00:00:00.000000+00:00' : null })),
]

const SEARCH_LISTS = {
  measured: prepareStations(searchColumns(SEARCH_MEASURED), reportsIn),
  ghcn: prepareStations(searchColumns(SEARCH_GHCN), reportsIn),
}

/** What `GET /_search/stations` answers: the real matching, on the mock's lists, for the lists that are asked for */
function stationSearch(url: URL): StationSearchAnswer {
  const query = url.searchParams.get('q') ?? ''
  const limit = Number(url.searchParams.get('limit') ?? 4)
  // the lists the reader chose that the server keeps (the forecast's points are the backend's own search by name, `/api/stations?name=`)
  const lists = (url.searchParams.get('lists') ?? 'ghcn').split(',')
  const networks = (['measured', 'ghcn'] as const)
    .filter(network => lists.includes(network))
    .map(network => ({ network, ...searchPrepared(SEARCH_LISTS[network], query, limit) }))
    .filter(found => found.total > 0)
  return { query, networks, pending: [], failed: [] }
}

/**
 * What `GET /api/station-ids` answers: the stations of several networks that carry the id, as the backend lists them: Hamburg-Fuhlsbüttel's for
 * 10147 and EDDH (which the lists of the search have too), and Berlin-Dahlem's for any other id (10381 is its WMO number)
 */
function stationIds(url: URL) {
  const asked = ['wmo_id', 'wigos_id', 'icao_id'].map(name => url.searchParams.get(name)).find(Boolean) ?? ''
  const hamburg = /10147|EDDH/.test(asked)
  const row = (extra: Record<string, unknown>) => ({ resolution: 'daily', dataset: 'climate_summary', elevation: 50, wmo_id: hamburg ? '10147' : '10381', wigos_id: hamburg ? '0-20000-0-10147' : '0-20000-0-10381', icao_id: hamburg ? 'EDDH' : null, matched_by: 'wmo_id', match: 'direct', ...extra })
  return {
    stations: hamburg
      ? [
          row({ provider: 'dwd', network: 'mosmix', resolution: 'hourly', dataset: 'large', station_id: '10147', name: 'HAMBURG-FUHLSBUETTEL', latitude: 53.63, longitude: 10 }),
          row({ provider: 'dwd', network: 'observation', station_id: '01975', name: 'Hamburg-Fuhlsbüttel', latitude: 53.6332, longitude: 9.9881 }),
          row({ provider: 'noaa', network: 'ghcn', resolution: 'daily', dataset: 'data', station_id: 'GM000010147', name: 'HAMBURG FUHLSBUETTEL', latitude: 53.635, longitude: 9.99, match: 'equivalent' }),
          row({ provider: 'aemet', network: 'observation', resolution: 'hourly', dataset: 'temperature_air', station_id: 'SN99999', name: 'HAMBURG (TEST)', latitude: 53.6, longitude: 10, match: 'equivalent' }),
        ]
      : [
          row({ provider: 'dwd', network: 'mosmix', resolution: 'hourly', dataset: 'large', station_id: '10381', name: 'BERLIN-DAHLEM (FU)', latitude: 52.46, longitude: 13.3 }),
          row({ provider: 'dwd', network: 'observation', station_id: '00403', name: 'Berlin-Dahlem (FU)', latitude: 52.4537, longitude: 13.3017 }),
          row({ provider: 'noaa', network: 'ghcn', resolution: 'daily', dataset: 'data', station_id: 'GM000010381', name: 'BERLIN-DAHLEM', latitude: 52.4537, longitude: 13.3017, match: 'equivalent' }),
          row({ provider: 'aemet', network: 'observation', resolution: 'daily', dataset: 'data', station_id: '4358', name: 'BERLIN (TEST)', latitude: 52.5, longitude: 13.4, match: 'equivalent' }),
        ],
  }
}

/** The stripes of a station as a fixture: the years and what they are of (the app makes the classes of them itself) */
function stripesValues(station: string | null, method: 'midrange' | 'tavg' | null = null): StripesFixture {
  const found = [...STRIPES_STATIONS, ...GHCN_STRIPES_STATIONS].find(candidate => candidate.station_id === station) ?? STRIPES_STATIONS[0]!
  return {
    // the part of the answer's `metadata` the stripes read: who the data is from, under which licence (the table's file carries both, GH-4233)
    metadata: {
      provider: {
        name_local: 'Deutscher Wetterdienst',
        name_english: 'German Weather Service',
        country: 'Germany',
        copyright: '© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)',
        url: 'https://www.dwd.de',
        license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' },
        attribution: 'Source: Deutscher Wetterdienst',
      },
    } as StripesFixture['metadata'],
    series: { station: found, unit: 'degree_celsius', method },
    // a warming curve with a wobble, so the stripes run from blue to red
    ...stripesAnswer(Array.from({ length: 70 }, (_, index) => ({
      year: 1955 + index,
      value: Math.round((7.5 + index * 0.03 + 0.8 * Math.sin(index / 3)) * 100) / 100,
    }))),
  }
}

const HISTORY: HistoryResponse = {
  histories: [{
    station_id: '00011',
    name: {
      station: [
        { station_id: '00011', station_name: 'Donaueschingen (Landeplatz)', valid_from: '1980-09-01T00:00:00+00:00', valid_to: null },
        { station_id: '00011', station_name: 'Donaueschingen', valid_from: '1970-01-01T00:00:00+00:00', valid_to: '1980-08-31T00:00:00+00:00' },
      ],
      operator: [
        { station_id: '00011', operator_name: 'Deutscher Wetterdienst', valid_from: '1970-01-01T00:00:00+00:00', valid_to: null },
      ],
    },
    geography: [{
      station_id: '00011',
      station_elevation: 680,
      latitude: 47.9737,
      longitude: 8.5205,
      valid_from: '1980-09-01T00:00:00+00:00',
      valid_to: null,
      station_name: 'Donaueschingen (Landeplatz)',
    }],
  }],
}

/** The answers a state starts from: a backend with the DWD observation data and nothing else wrong */
export function defaultHandlers(now: Date = new Date()): Handlers {
  return {
    'version': () => ({
      version: '0.0.0-accessibility',
      mcp_enabled: false,
      limits: { max_stations: 100, max_rows: 500_000, max_stream_rows: 10_000_000, timeout: 60, max_concurrent: 32 },
    }),
    'coverage': () => OBSERVATION_COVERAGE,
    'auth': url => ({ provider: url.searchParams.get('provider'), network: url.searchParams.get('network'), auth: false, configured: false, valid: true }),
    // a server that does not report its settings: the app takes wetterdienst's own
    'settings': () => new ApiFailure(404, 'Not Found'),
    'stations': (url) => {
      const mosmix = url.searchParams.get('network') === 'mosmix'
      // the stations of the snow forecast, which the Forecast asks for once: the few of the dataset and not the list
      if (mosmix && url.searchParams.get('parameters') === 'hourly/snow')
        return { stations: SNOW_STATIONS }
      // a list is comma-separated, and the key given more than once is read as the same list
      const wanted = url.searchParams.getAll('stations').flatMap(ids => ids.split(','))
      // the stations of the snow forecast are MOSMIX stations that a link can name; they are not in the lists the pickers show
      const all = mosmix ? (wanted.length ? [...MOSMIX_STATIONS, ...SNOW_STATIONS] : MOSMIX_STATIONS) : STATIONS
      // a place by its name: the backend answers its best five matches, here the ones whose name holds the text
      const name = url.searchParams.get('name')?.toLowerCase()
      if (name)
        return { stations: all.filter(station => station.name?.toLowerCase().includes(name)).slice(0, 5) }
      return { stations: wanted.length ? all.filter(station => wanted.includes(station.station_id)) : all }
    },
    'values': (url) => {
      if (isSnowRequest(url))
        return snowValues(url, now)
      return { values: url.searchParams.get('network') === 'mosmix' ? forecastValues(url, now) : observationValues(url) }
    },
    'issues': () => ({ issues: ['2026-10-14T09:00:00+00:00', '2026-10-14T15:00:00+00:00', '2026-10-14T21:00:00+00:00'] }),
    'history': () => HISTORY,
    'glossary': () => GLOSSARY,
    'providers': () => PROVIDER_LIST,
    'stripes/stations': () => ({ stations: STRIPES_STATIONS }),
    'stripes/values': url => stripesValues(url.searchParams.get('stations')),
    '_ghcn/stations': () => ({ stations: GHCN_STRIPES_STATIONS }),
    // the search of the header (GH-3790): the app's own server's matching of the lists, and the backend's search of every network for an id
    '_search/stations': stationSearch,
    'station-ids': stationIds,
    // the list of the stations of GHCN daily as the app's server hands it to the map, as columns (GH-4267)
    '_ghcn/map-stations': () => searchColumns(SEARCH_GHCN),
    '_ghcn/annual': url => stripesValues(url.searchParams.get('station'), 'midrange'),
    // the usual scan of the thunderstorm cells: none (GH-4208), and the radar's loop of 49 frames, each an image of cells of rain that drift east (GH-3788)
    'storm-cells': () => emptyScan(),
    'radar/frames': () => radarAnswer({ now: now.getTime() }),
    'radar/frame': (url) => {
      const start = Math.floor(now.getTime() / 300_000) * 300_000
      return new ApiBinary(radarPng((Date.parse(url.searchParams.get('time') ?? '') - start) / 60_000), 'image/png', { 'cache-control': 'public, max-age=3600' })
    },
  }
}

// 1x1 transparent PNG: what a map tile, an avatar or a marker icon is answered with, so that the
// page lays out as it does with them and nothing leaves the machine
const PIXEL = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
)

export interface Backend {
  handlers: Handlers
  /** The `/api/*` paths asked for that no handler answers */
  unanswered: string[]
  /** Resolves once no `/api/*` request has been under way or answered for a while: the page has what it asked for */
  idle: () => Promise<void>
}

/** The key of the handler of a request: its path under `/api/`, `/_ghcn/` and `/_search/` kept, and the requests for the annual record the stripes' keys */
function keyOf(url: URL): string {
  const path = url.pathname.replace(/^\/api\//, '').replace(/^\//, '')
  const annual = url.searchParams.get('parameters')?.startsWith('annual/')
  return annual && path === 'stations' ? 'stripes/stations' : annual && path === 'values' ? 'stripes/values' : path
}

/** How long the page is left alone after its last request was answered, for what it does with the answer */
const QUIET_MS = 300

/**
 * Answers every `/api/*` request of `page`, which the app serves at `baseURL`, from `handlers`, and
 * every request to another host with a transparent pixel (images) or a refusal (anything else).
 * `override` replaces handlers of the default set, per `/api/<path>`.
 */
export async function mockBackend(
  page: Page,
  baseURL: string,
  override: Handlers = {},
  /** The instant the forecast starts at: the one the page's clock is set to, if the test sets it (default: the real now) */
  now: Date = new Date(),
): Promise<Backend> {
  const origin = new URL(baseURL).origin
  let inFlight = 0
  let lastAnswer = Date.now()
  const backend: Backend = {
    handlers: { ...defaultHandlers(now), ...override },
    unanswered: [],
    idle: async () => {
      const busy = () => inFlight > 0 || Date.now() - lastAnswer < QUIET_MS
      while (busy())
        await page.waitForTimeout(50)
    },
  }

  await page.route(
    url => url.origin === origin && (url.pathname.startsWith('/api/') || url.pathname.startsWith('/_ghcn/') || url.pathname.startsWith('/_search/')),
    async (route) => {
      inFlight++
      try {
        const url = new URL(route.request().url())
        const key = keyOf(url)
        const handler = backend.handlers[key]
        if (!handler) {
          backend.unanswered.push(url.pathname)
          await route.fulfill({ status: 501, json: { detail: `not mocked: ${url.pathname}` } })
          return
        }
        const answer = await handler(url, route)
        // the stripes' data is written as a fixture and answered as the API does
        const body = key === 'stripes/values' ? valuesOfFixture(answer) : key === '_ghcn/annual' ? ghcnAnnualOfFixture(answer) : answer
        if (body instanceof ApiFailure)
          await route.fulfill({ status: body.status, json: { ...body.extra, detail: body.detail } })
        else if (body instanceof ApiBinary)
          await route.fulfill({ status: 200, body: body.body, contentType: body.contentType, headers: body.headers })
        else
          await route.fulfill({ status: 200, json: body })
      }
      finally {
        inFlight--
        lastAnswer = Date.now()
      }
    },
  )

  // everything that is not the app itself
  await page.route(
    url => url.origin !== origin && url.protocol.startsWith('http'),
    async (route) => {
      if (route.request().resourceType() === 'image')
        await route.fulfill({ status: 200, contentType: 'image/png', body: PIXEL })
      else
        await route.abort()
    },
  )

  return backend
}

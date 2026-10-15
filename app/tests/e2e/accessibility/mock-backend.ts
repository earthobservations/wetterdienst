import type { Page, Route } from '@playwright/test'
import type {
  CoverageResponse,
  GlossaryEntry,
  HistoryResponse,
  ProviderNetworkCoverageResponse,
  Station,
  StripesStation,
  StripesValuesResponse,
  Value,
} from '../../../shared/types/api'
import { Buffer } from 'node:buffer'

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

/** The answers by `/api/<path>`, to be replaced one by one where a state needs a different one */
export type Handlers = Record<string, Handler>

/** What a handler returns to answer with an error instead of a body */
export class ApiFailure {
  constructor(readonly status: number, readonly detail: string) {}
}

const PROVIDERS: CoverageResponse = {
  dwd: {
    observation: { auth: false, configured: false, valid: null, date_required: false },
    mosmix: { auth: false, configured: false, valid: null, date_required: false },
  },
  noaa: {
    ghcn: { auth: false, configured: false, valid: null, date_required: false },
  },
}

function parameter(name: string, name_original: string, unit_type: string, unit: string, description: string) {
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

/** Daily climate summary of the stations the explorer, the history and the maps are shown with */
export const STATIONS: Station[] = [
  { station_id: '00011', name: 'Donaueschingen (Landeplatz)', region: 'Baden-Württemberg', latitude: 47.9737, longitude: 8.5205, elevation: 680, start_timestamp: '1980-09-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00044', name: 'Großenkneten', region: 'Niedersachsen', latitude: 52.9336, longitude: 8.2370, elevation: 44, start_timestamp: '1971-03-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00071', name: 'Albstadt-Badkap', region: 'Baden-Württemberg', latitude: 48.2156, longitude: 8.9784, elevation: 759, start_timestamp: '1986-11-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00073', name: 'Aldersbach-Kriestorf', region: 'Bayern', latitude: 48.6159, longitude: 13.0506, elevation: 340, start_timestamp: '1964-01-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00091', name: 'Alfhausen', region: 'Niedersachsen', latitude: 52.4853, longitude: 7.9126, elevation: 65, start_timestamp: '1993-01-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00096', name: 'Neuhaus am Rennweg', region: 'Thüringen', latitude: 50.5063, longitude: 11.1283, elevation: 840, start_timestamp: '2004-12-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00102', name: 'Leuchtturm Alte Weser', region: 'Niedersachsen', latitude: 53.8633, longitude: 8.1275, elevation: 3, start_timestamp: '1997-01-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00125', name: 'Andechs-Rothenfeld', region: 'Bayern', latitude: 47.9794, longitude: 11.1888, elevation: 680, start_timestamp: '2004-12-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00131', name: 'Angermünde', region: 'Brandenburg', latitude: 53.0301, longitude: 13.9951, elevation: 54, start_timestamp: '1991-03-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00183', name: 'Arkona', region: 'Mecklenburg-Vorpommern', latitude: 54.6791, longitude: 13.4343, elevation: 42, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00198', name: 'Artern', region: 'Thüringen', latitude: 51.3745, longitude: 11.2915, elevation: 164, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: '2018-12-31T00:00:00+00:00' },
  { station_id: '00205', name: 'Aue', region: 'Sachsen', latitude: 50.5919, longitude: 12.7095, elevation: 450, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: null },
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

const MOSMIX_STATIONS: Station[] = [
  MOSMIX_STATION,
  { station_id: '10147', name: 'HAMBURG-FUHLSBUETTEL', region: null, latitude: 53.63, longitude: 10.0, elevation: 11, start_timestamp: null, end_timestamp: null },
  { station_id: '10384', name: 'BERLIN-TEMPELHOF', region: null, latitude: 52.47, longitude: 13.4, elevation: 49, start_timestamp: null, end_timestamp: null },
  { station_id: '10865', name: 'MUENCHEN-STADT', region: null, latitude: 48.16, longitude: 11.54, elevation: 515, start_timestamp: null, end_timestamp: null },
]

const STRIPES_STATIONS: StripesStation[] = STATIONS.slice(0, 6).map(station => ({
  station_id: station.station_id,
  name: station.name as string,
  region: station.region as string,
  latitude: station.latitude as number,
  longitude: station.longitude as number,
  start_timestamp: '1950-01-01T00:00:00+00:00',
  end_timestamp: null,
}))

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
  const stations = (url.searchParams.getAll('station').join(',') || '00011').split(',')
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

/** Three days of hourly MOSMIX values from this hour on, for each series the meteogram draws */
function forecastValues(url: URL): Value[] {
  const station_id = url.searchParams.get('station') ?? MOSMIX_STATION.station_id
  const start = new Date()
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
    pressure_air_site_reduced: hour => 1012 + 4 * Math.sin(hour / 20),
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

function stripesValues(station: string | null): StripesValuesResponse {
  const found = STRIPES_STATIONS.find(candidate => candidate.station_id === station) ?? STRIPES_STATIONS[0]!
  return {
    metadata: { station: found, resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m' },
    values: Array.from({ length: 70 }, (_, index) => ({
      timestamp: `${1955 + index}-01-01T00:00:00+00:00`,
      // a warming curve with a wobble, so the stripes run from blue to red
      value: Math.round((7.5 + index * 0.03 + 0.8 * Math.sin(index / 3)) * 100) / 100,
    })),
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
export function defaultHandlers(): Handlers {
  return {
    'version': () => ({ version: '0.0.0-accessibility', mcp_enabled: false }),
    'coverage': (url) => {
      if (!url.searchParams.get('provider'))
        return PROVIDERS
      return OBSERVATION_COVERAGE
    },
    'auth': url => ({ provider: url.searchParams.get('provider'), network: url.searchParams.get('network'), auth: false, configured: false, valid: true }),
    // a server that does not report its settings: the app takes wetterdienst's own
    'settings': () => new ApiFailure(404, 'Not Found'),
    'stations': (url) => {
      const mosmix = url.searchParams.get('network') === 'mosmix'
      const all = mosmix ? MOSMIX_STATIONS : STATIONS
      const wanted = url.searchParams.getAll('station')
      return { stations: wanted.length ? all.filter(station => wanted.includes(station.station_id)) : all }
    },
    'values': url => ({ values: url.searchParams.get('network') === 'mosmix' ? forecastValues(url) : observationValues(url) }),
    'issues': () => ({ issues: ['2026-10-14T09:00:00+00:00', '2026-10-14T15:00:00+00:00', '2026-10-14T21:00:00+00:00'] }),
    'history': () => HISTORY,
    'glossary': () => GLOSSARY,
    'stripes/stations': () => ({ stations: STRIPES_STATIONS }),
    'stripes/values': url => stripesValues(url.searchParams.get('station')),
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

/** How long the page is left alone after its last request was answered, for what it does with the answer */
const QUIET_MS = 300

/**
 * Answers every `/api/*` request of `page`, which the app serves at `baseURL`, from `handlers`, and
 * every request to another host with a transparent pixel (images) or a refusal (anything else).
 * `override` replaces handlers of the default set, per `/api/<path>`.
 */
export async function mockBackend(page: Page, baseURL: string, override: Handlers = {}): Promise<Backend> {
  const origin = new URL(baseURL).origin
  let inFlight = 0
  let lastAnswer = Date.now()
  const backend: Backend = {
    handlers: { ...defaultHandlers(), ...override },
    unanswered: [],
    idle: async () => {
      const busy = () => inFlight > 0 || Date.now() - lastAnswer < QUIET_MS
      while (busy())
        await page.waitForTimeout(50)
    },
  }

  await page.route(
    url => url.origin === origin && url.pathname.startsWith('/api/'),
    async (route) => {
      inFlight++
      try {
        const url = new URL(route.request().url())
        const handler = backend.handlers[url.pathname.replace(/^\/api\//, '')]
        if (!handler) {
          backend.unanswered.push(url.pathname)
          await route.fulfill({ status: 501, json: { detail: `not mocked: ${url.pathname}` } })
          return
        }
        const body = await handler(url, route)
        if (body instanceof ApiFailure)
          await route.fulfill({ status: body.status, json: { detail: body.detail } })
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

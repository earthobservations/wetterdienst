import type { Handlers } from './mock-backend'
import { DateTime } from 'luxon'
import { defaultHandlers } from './mock-backend'

// What the Compare tool (GH-4296) and the two comparisons of Ask the weather are answered from, as the mock backend gives it:
// the daily and monthly climate summary of the stations of the mock, with the unit and the aggregation of each parameter in the answer's
// `metadata`, small and fixed. A station has its own level, and every year its own, so that two stations and two periods differ by a known
// amount; two days are missing on purpose (a null on the 5th of each month at 00044, no row at all on the 6th at 00071).

/** Every request the comparison made, by path and its query */
export interface CompareAsked {
  path: string
  query: Record<string, string>
}

/** The level of a station's mean temperature: Donaueschingen is cold (680 m), Großenkneten mild (44 m): 4 °C apart, as the mock's two stations show */
export const LEVEL: Record<string, number> = { '00011': 8, '00044': 12, '00071': 9, '02564': 12, '02597': 11 }

const PARAMETERS = {
  temperature_air_mean_2m: { unit: '°C', aggregation: 'mean', unit_type: 'temperature', name_original: 'tmk', description: 'Daily mean of temperature at 2 m height.' },
  precipitation_amount: { unit: 'mm', aggregation: 'sum', unit_type: 'precipitation', name_original: 'rsk', description: 'Daily precipitation height.' },
} as const
type Name = keyof typeof PARAMETERS

function isName(value: string): value is Name {
  return value in PARAMETERS
}

/** The value of a station on a day: its level, a slow swing, and a step of 1.5 for every year since 2025 (so two years of one station differ) */
export function mockValue(station: string, name: Name, day: DateTime): number {
  const year = day.year - 2025
  if (name === 'precipitation_amount')
    // a day of the month decides the amount, not the date's place in the year: the same day of two years differs by 0.5 mm for each year between
    return Math.round((1 + 0.5 * year + 0.3 * (day.day % 3) + (station === '00044' ? 1 : 0)) * 10) / 10
  return Math.round(((LEVEL[station] ?? 10) + 3 * Math.sin(day.ordinal / 6) + 1.5 * year) * 10) / 10
}

/** The rows of the stations for a window `YYYY-MM-DD/YYYY-MM-DD`, daily or monthly, in the long shape of `/api/values` */
export function climateRows(stations: string[], name: Name, resolution: 'daily' | 'monthly', window: string) {
  const [from, to] = window.split('/') as [string, string]
  const rows = []
  const last = DateTime.fromISO(to, { zone: 'utc' })
  for (const station_id of stations) {
    let day = DateTime.fromISO(from, { zone: 'utc' })
    if (resolution === 'monthly')
      day = day.startOf('month')
    while (day <= last) {
      const missing = resolution === 'daily' && station_id === '00071' && day.day === 6
      const empty = resolution === 'daily' && station_id === '00044' && day.day === 5
      if (!missing) {
        rows.push({
          station_id,
          resolution,
          dataset: 'climate_summary',
          parameter: name,
          timestamp: `${day.toISODate()}T00:00:00+00:00`,
          value: empty ? null : mockValue(station_id, name, day),
          quality_flags: null,
        })
      }
      day = resolution === 'monthly' ? day.plus({ months: 1 }) : day.plus({ days: 1 })
    }
  }
  return rows
}

/** The answer's `metadata.parameters` for a parameter */
export function parameterInfo(name: Name, resolution: string) {
  const { unit, aggregation } = PARAMETERS[name]
  return { resolution, dataset: 'climate_summary', name, name_original: PARAMETERS[name].name_original, description: null, quantity: PARAMETERS[name].unit_type, unit, aggregation, timestamp_position: 'start' }
}

/** Whether a `values` request is for the daily or monthly climate summary of DWD's observations that the comparison reads: its window, stations and parameter */
export function climateRequest(url: URL) {
  const [resolution, dataset, name] = (url.searchParams.get('parameters') ?? '').split('/')
  const window = url.searchParams.get('timestamp')
  if (url.searchParams.get('network') !== 'observation' || dataset !== 'climate_summary' || !name || !isName(name) || !window || !['daily', 'monthly'].includes(resolution ?? ''))
    return null
  return { name, resolution: resolution as 'daily' | 'monthly', window, stations: (url.searchParams.get('stations') ?? '').split(',').filter(Boolean) }
}

/** The answer of a comparison request, with the metadata the Explorer reads the unit from */
export function climateAnswer(request: NonNullable<ReturnType<typeof climateRequest>>) {
  return {
    metadata: { parameters: [parameterInfo(request.name, request.resolution)] },
    values: climateRows(request.stations, request.name, request.resolution, request.window),
  }
}

/** The coverage of DWD's observations with the monthly climate summary the comparison supports, besides the daily one */
function coverage(url: URL, base: NonNullable<Handlers['coverage']>) {
  const answer = structuredClone(base(url, undefined as never)) as Record<string, any>
  if (url.searchParams.get('provider') !== 'dwd' || url.searchParams.get('network') !== 'observation')
    return answer
  const parameters = (Object.keys(PARAMETERS) as Name[]).map(name => ({ name, name_original: PARAMETERS[name].name_original, unit_type: PARAMETERS[name].unit_type, unit: PARAMETERS[name].unit, description: PARAMETERS[name].description }))
  for (const resolution of ['daily', 'monthly'])
    answer[resolution] = { description: null, datasets: { climate_summary: { description: 'Station observations for Germany.', parameters } } }
  return answer
}

/** A backend for the Compare tool: the comparison's data, the monthly climate summary besides the daily one, and what was asked recorded */
export function compareHandlers(asked: CompareAsked[] = []): Handlers {
  const base = defaultHandlers()
  return {
    coverage: url => coverage(url, base.coverage!),
    values: (url, route) => {
      asked.push({ path: 'values', query: Object.fromEntries(url.searchParams) })
      const request = climateRequest(url)
      return request ? climateAnswer(request) : base.values!(url, route)
    },
  }
}

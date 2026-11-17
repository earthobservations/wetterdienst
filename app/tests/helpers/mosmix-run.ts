import { readFileSync } from 'node:fs'

/**
 * Real MOSMIX-L runs, for the tests of the forecast's late days (GH-4175): files of DWD's opendata, taken on 2026-11-17 and kept
 * as the hours after the issue of each value that has one (`mosmix-precipitation-runs.json`: the four precipitation elements of
 * four stations in three runs; `mosmix-10382-run.json`: every series the forecast asks for, 10382 in the run of 03 UTC, whose
 * hourly amount `RR1c` is 0.0 from +112 h while its 6, 12 and 24 h totals still carry rain).
 */
type Steps = [number, number][]

interface PrecipitationRun {
  issue: string
  [parameter: string]: Steps | string
}

interface FullRun {
  station_id: string
  issue: string
  series: Record<string, Steps>
}

const read = <T>(name: string): T => JSON.parse(readFileSync(new URL(name, import.meta.url), 'utf8')) as T

export const PRECIPITATION = {
  hour: 'precipitation_amount_significant_weather_last_1h',
  six: 'precipitation_amount_significant_weather_last_6h',
  twelve: 'precipitation_amount_significant_weather_last_12h',
  day: 'precipitation_amount_significant_weather_last_24h',
} as const

export interface RunValue {
  station_id: string
  resolution: 'hourly'
  dataset: 'large'
  parameter: string
  timestamp: string
  value: number | null
  quality_flags: null
}

const stamp = (issue: string, hours: number, shiftDays: number) => new Date(Date.parse(issue) + (hours + shiftDays * 24) * 3_600_000).toISOString().replace('.000Z', '+00:00')

/** The four precipitation series of a station in a run (`10382@2026-11-17 03 UTC`), as `Value`s of the answer */
export function precipitationRunValues(key: string, shiftDays = 0): RunValue[] {
  const run = read<Record<string, PrecipitationRun>>('./mosmix-precipitation-runs.json')[key]
  if (!run)
    throw new Error(`no run ${key}`)
  const station = key.split('@')[0]!
  return Object.values(PRECIPITATION).flatMap(parameter =>
    (run[parameter] as Steps).map(([hours, value]) => ({ station_id: station, resolution: 'hourly' as const, dataset: 'large' as const, parameter, timestamp: stamp(run.issue, hours, shiftDays), value, quality_flags: null })),
  )
}

/** The keys of the runs in `mosmix-precipitation-runs.json` */
export function precipitationRunKeys(): string[] {
  return Object.keys(read<Record<string, PrecipitationRun>>('./mosmix-precipitation-runs.json'))
}

export interface FullRunOptions {
  /** every stamp moved by this many whole days, which keeps the hours on the 00, 06, 12, 18 UTC grid */
  shiftDays?: number
  /** the series to leave out, by the parameter name */
  without?: string[]
  /** the station id the values carry */
  stationId?: string
}

/** The issue of the full run of 10382: the stamps start an hour after it */
export const RUN_10382_ISSUE = '2026-11-17T03:00:00+00:00'

/** Every series the forecast asks for in the run of 10382 at 03 UTC on 2026-11-17, 247 hours, as `Value`s of the answer in the app's default units */
export function run10382Values({ shiftDays = 0, without = [], stationId }: FullRunOptions = {}): RunValue[] {
  const run = read<FullRun>('./mosmix-10382-run.json')
  return Object.entries(run.series)
    .filter(([parameter]) => !without.includes(parameter))
    .flatMap(([parameter, steps]) => steps.map(([hours, value]) => ({ station_id: stationId ?? run.station_id, resolution: 'hourly' as const, dataset: 'large' as const, parameter, timestamp: stamp(run.issue, hours, shiftDays), value, quality_flags: null })))
}

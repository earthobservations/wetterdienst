/**
 * What the generic API and the app's own server answer for the stripes' tests (GH-4258): the stripes are made by the app of the
 * annual values (`/api/values` for DWD, `/_ghcn/annual` for GHCN daily), so a test serves those, from the record it wants
 * stripes of. The functions here write each answer as the API writes it; `stripesAnswer` (`./stripes-answer`) says what the app
 * makes of the record.
 */
import type { YearValue } from './stripes-answer'
import { yearTimestamp } from '../../app/utils/stripes-scale'

export const PROVIDER_DWD = {
  name_local: 'Deutscher Wetterdienst',
  attribution: 'Source: Deutscher Wetterdienst',
  license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' },
}

export const PROVIDER_NOAA = {
  name_local: 'National Oceanic And Atmospheric Administration',
  attribution: 'NOAA National Centers for Environmental Information (NCEI), Global Historical Climatology Network',
  license: { spdx_id: 'CC0-1.0', name: 'Creative Commons Zero v1.0 Universal', url: 'https://creativecommons.org/publicdomain/zero/1.0/' },
}

/** A record, as a test writes it: the years, or the items of an old answer, with the years that have no value null */
export type Record_ = YearValue[] | Array<{ timestamp: string | null, value: number | null }>

function yearsOf(record: Record_): YearValue[] {
  return record.map(item => 'year' in item ? item : { year: new Date(item.timestamp!).getUTCFullYear(), value: item.value })
}

/** The unit the answer names the values in, as `/api/values` writes it in the metadata of its parameters */
export interface ValuesOptions {
  unit?: string
  parameter?: string
  /** The provider's block of the metadata, the DWD's by default; null where the answer carries none */
  provider?: Partial<typeof PROVIDER_DWD> | null
  stationId?: string
  /** The `quality_flags` of each reading */
  flags?: string
}

/** The answer of `/api/values` for the annual values of one station: a row for each year that has a value */
export function valuesAnswer(record: Record_, options: ValuesOptions = {}) {
  const parameter = options.parameter ?? 'temperature_air_mean_2m'
  return {
    metadata: {
      ...(options.provider === null ? {} : { provider: options.provider ?? PROVIDER_DWD }),
      parameters: [{ name: parameter, unit: options.unit ?? '°C' }],
      warnings: [],
    },
    values: yearsOf(record).filter(item => item.value !== null).map(item => ({
      station_id: options.stationId ?? '1048',
      resolution: 'annual',
      dataset: 'climate_summary',
      parameter,
      timestamp: yearTimestamp(item.year),
      value: item.value,
      quality_flags: options.flags ?? '1',
    })),
  }
}

/**
 * The warning the backend gives where NCEI did not answer and the days of a station were read from the mirror of NOAA's data on AWS
 * (GH-4230), as the answer of its generic API carries it
 */
export const SOURCE_FALLBACK_WARNING = {
  code: 'source-fallback',
  message: 'The file of station GM000010147 was not read from NOAA NCEI (it answered 503) and comes from the AWS mirror instead, whose files may be older: the most recent days of this station may be missing. Try again later.',
  stations: ['GM000010147'],
}

/** The answer of `/_ghcn/annual`: a row for every year, the value null where the year fails the rules; `mirror` for days read from the mirror on AWS */
export function ghcnAnnualAnswer(record: Record_, options: { unit?: string, parameter?: string, method?: 'midrange' | 'tavg' | null, stationId?: string, mirror?: boolean } = {}) {
  return {
    metadata: { provider: PROVIDER_NOAA, ...(options.mirror ? { warnings: [SOURCE_FALLBACK_WARNING] } : {}) },
    series: { station_id: options.stationId ?? 'GM000010147', parameter: options.parameter ?? 'temperature_air_mean_2m', unit: options.unit ?? '°C', method: options.method ?? null },
    values: yearsOf(record).map(item => ({ timestamp: yearTimestamp(item.year), value: item.value })),
  }
}

/** The records of the years `first` to `last`, a value for each from `valueOf` (the years in `gaps` have none) */
export function record(first: number, last: number, valueOf: (year: number) => number, gaps: number[] = []): YearValue[] {
  return Array.from({ length: last - first + 1 }, (_, index) => first + index)
    .map(year => ({ year, value: gaps.includes(year) ? null : valueOf(year) }))
}

/** What a test of the page writes as the answer for a station's stripes: the years with their values (the app makes their classes itself), the unit, the station and the provider's block */
export interface StripesFixture {
  values: Array<{ timestamp: string | null, value: number | null }>
  series?: { unit?: string, station?: { station_id?: string }, method?: 'midrange' | 'tavg' | null }
  metadata?: { provider?: Partial<typeof PROVIDER_DWD> }
  /** The days were read from the mirror of NOAA's data on AWS: `/_ghcn/annual` carries the `source-fallback` warning (GH-4390) */
  mirror?: boolean
}

export const isFixture = (answer: unknown): answer is StripesFixture => !!answer && Array.isArray((answer as StripesFixture).values)

/** The answer of `/api/values` for a fixture of a station's stripes, and any other answer (a failure's body) as it is */
export function valuesOfFixture(answer: unknown) {
  return isFixture(answer)
    ? valuesAnswer(answer.values, {
        unit: answer.series?.unit,
        stationId: answer.series?.station?.station_id,
        // a test that gives no provider's block has an answer that carries none
        provider: answer.metadata?.provider ? { ...PROVIDER_DWD, ...answer.metadata.provider } : null,
      })
    : answer
}

/** The answer of `/_ghcn/annual` for a fixture, where the series names how the days were made, and any other answer as it is */
export function ghcnAnnualOfFixture(answer: unknown) {
  return isFixture(answer)
    ? ghcnAnnualAnswer(answer.values, { unit: answer.series?.unit, stationId: answer.series?.station?.station_id, method: answer.series?.method, mirror: answer.mirror })
    : answer
}

/** Wraps a handler of an endpoint, which may be asynchronous, set a status or throw, so that what it answers is converted */
function answering<E>(handler: (event: E) => unknown, convert: (answer: unknown) => unknown) {
  return (event: E) => {
    const answer = handler(event)
    return answer instanceof Promise ? answer.then(convert) : convert(answer)
  }
}

/**
 * The handler of `/api/values` for a test that writes the stripes of a station as `{ series, values }`: it answers the annual
 * values of those years, as the API does, and an answer that is no such fixture (a failure's body) as it is.
 */
export function asValues<E>(handler: (event: E) => unknown) {
  return answering(handler, valuesOfFixture)
}

/** The same for `/_ghcn/annual` */
export function asGhcnAnnual<E>(handler: (event: E) => unknown) {
  return answering(handler, ghcnAnnualOfFixture)
}

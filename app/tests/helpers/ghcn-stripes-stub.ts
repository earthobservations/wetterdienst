/**
 * A stand-in for the days of a station of NOAA GHCN daily, written as `/api/values` gives them, for the tests of the annual values
 * the app's server calculates from them (GH-4258). It is the port of `tests/ui/ghcn_stripes_stub.py` of the backend (removed by
 * GH-4258), which its own tests of the stripes read through the library, and so the numbers are the same: a station whose annual mean
 * temperature is 10.0 degrees in `FIRST_YEAR` and 0.2 more with each year after it (a TMAX of 15.0 and a TMIN of 5.0, plus 0.2 a
 * year each, that swing against each other so that the mean of a day is the same every day), and 1.0 and 3.0 mm of rain on
 * alternate days. So a year's temperature is known without calculating it, and a year the rules fail is the only way it differs.
 */
import type { DailyRow } from '../../server/utils/ghcnAnnual'

/** The station every test of the stripes reads, and the years of its record */
export const STATION = 'USW00000001'
export const FIRST_YEAR = 1990
export const LAST_YEAR = 2020

/** The station that has TAVG and no TMAX and TMIN */
export const TAVG_ONLY_STATION = 'USW00000002'

/** The one year that has a TAVG on every day, 1.0 degree below the (TMAX + TMIN) / 2 of the year; the series is the midrange all the same, so this year is no step in it */
export const TAVG_YEAR = 2015

const DAY_MS = 86_400_000
const iso = (date: Date) => date.toISOString().slice(0, 10)
const utc = (year: number, month: number, day: number) => new Date(Date.UTC(year, month - 1, day))
/** Python's `date.toordinal()`: 1 January 0001 is 1, 1 January 1970 is 719163 */
const ordinal = (date: Date) => Math.round(date.getTime() / DAY_MS) + 719_163
/** Python's `%`, which has the sign of the divisor */
const mod = (n: number, m: number) => ((n % m) + m) % m

function dates(from: Date, to: Date): Date[] {
  const result: Date[] = []
  for (let time = from.getTime(); time <= to.getTime(); time += DAY_MS)
    result.push(new Date(time))
  return result
}

/** 11 days of March 2000 with none next to another: more than the 10 a month may miss, in no run of more than 1 */
const TOO_MANY_DAYS_2000 = Array.from({ length: 11 }, (_, index) => iso(utc(2000, 3, 1 + 2 * index)))
/** 5 days of June 2005 in a row: fewer than 10, but more than the 4 a month may miss in a row */
const TOO_LONG_A_RUN_2005 = Array.from({ length: 5 }, (_, index) => iso(utc(2005, 6, 10 + index)))
/** 4 days in a row and 6 more apart, July 2010: 10 missing and none of them in a run of more than 4 */
const JUST_ENOUGH_2010 = [1, 2, 3, 4, 10, 12, 14, 16, 18, 20].map(day => iso(utc(2010, 7, day)))
/** The days the stub station has no row for, in the years 2000, 2005 and 2010 */
export const MISSING_DAYS = new Set([...TOO_MANY_DAYS_2000, ...TOO_LONG_A_RUN_2005, ...JUST_ENOUGH_2010])

/** The annual mean the stub station has in `year`, by the rules, where its days make it valid */
export const meanTemperature = (year: number) => 10 + 0.2 * (year - FIRST_YEAR)

/** The rain of a day in mm: 3.0 on a day of odd ordinal, 1.0 on the others, so that no series is stuck */
export const rainOn = (date: Date) => ordinal(date) % 2 ? 3 : 1

/** The annual precipitation the stub station has in `year`, by the rules, where its days make it valid */
export function rainOf(year: number): number {
  return dates(utc(year, 1, 1), utc(year, 12, 31)).reduce((sum, date) => sum + rainOn(date), 0)
}

/** The TAVG of a day in tenths: of every day at a station that has it alone, of `TAVG_YEAR` at the others */
function tavgOf(date: Date, midrange: number, onlyTavg: boolean): number | null {
  const swing = [-10, 0, 10, 0][mod(ordinal(date), 4)]!
  if (onlyTavg)
    return midrange + swing
  return date.getUTCFullYear() === TAVG_YEAR ? midrange - 10 + swing : null
}

/**
 * The rows of the stub station: a value for each of its readings in the unit `/api/values` gives (the tenths of the file divided
 * by ten), the flags as the provider writes them (`source:S`, and the quality flag `G` ahead of it for a reading that failed a check).
 *
 * @param options - `failed` are days whose TMAX and PRCP carry a quality flag, a check they failed; the record runs to `lastYear`; a station that has no TAVG at all (`tavg: false`) has no row of it; one that has TAVG alone (`onlyTavg`) has it on every day, and no TMAX and TMIN
 * @param options.failed - The days whose TMAX and PRCP failed a check, as `YYYY-MM-DD`
 * @param options.lastYear - The last year of the record
 * @param options.tavg - Whether the station has a TAVG
 * @param options.onlyTavg - Whether TAVG is all the station has
 */
export function stubRows(options: { failed?: Iterable<string>, lastYear?: number, tavg?: boolean, onlyTavg?: boolean } = {}): DailyRow[] {
  const failed = new Set(options.failed ?? [])
  const tavg = options.tavg ?? true
  const onlyTavg = options.onlyTavg ?? false
  const rows: DailyRow[] = []
  for (const date of dates(utc(FIRST_YEAR, 1, 1), utc(options.lastYear ?? LAST_YEAR, 12, 31))) {
    const key = iso(date)
    if (MISSING_DAYS.has(key))
      continue
    const steps = date.getUTCFullYear() - FIRST_YEAR
    // the two swing against each other, so that the mean of the day is the same every day (and no series is "stuck")
    const swing = [-15, -5, 5, 15][mod(ordinal(date), 4)]!
    const tmax = 150 + 2 * steps + swing
    const tmin = 50 + 2 * steps - swing
    const bad = failed.has(key)
    const cells: Array<[string, number | null, boolean]> = [
      ['precipitation_amount', Math.round(rainOn(date) * 10), bad],
      ['temperature_air_mean_2m', tavgOf(date, Math.floor((tmax + tmin) / 2), onlyTavg), false],
      ['temperature_air_max_2m', tmax, bad],
      ['temperature_air_min_2m', tmin, false],
    ]
    for (const [parameter, tenths, check] of cells) {
      if ((parameter === 'temperature_air_mean_2m' && !(tavg || onlyTavg)) || (onlyTavg && (parameter === 'temperature_air_max_2m' || parameter === 'temperature_air_min_2m')) || tenths === null)
        continue
      rows.push({ parameter, timestamp: `${key}T00:00:00.000000+00:00`, value: tenths / 10, quality_flags: check ? 'G,source:S' : 'source:S' })
    }
  }
  return rows
}

/** The days of `from` to `to` (both included) as `YYYY-MM-DD` */
export function daysBetween(from: string, to: string): string[] {
  return dates(new Date(`${from}T00:00:00Z`), new Date(`${to}T00:00:00Z`)).map(iso)
}

/** The year it is, which the stub's open records run to */
export const THIS_YEAR = new Date().getUTCFullYear()

/** The element each daily parameter of the generic API is, in the inventory of NOAA */
export const ELEMENT_OF: Record<string, string> = {
  temperature_air_mean_2m: 'TAVG',
  temperature_air_max_2m: 'TMAX',
  temperature_air_min_2m: 'TMIN',
  precipitation_amount: 'PRCP',
}

/**
 * The stations of the stub's lists, each with the span of its elements (the port of `LISTED` of `ghcn_stripes_stub.py`):
 * (id, latitude, longitude, name, [(element, first year, last year)])
 */
export const LISTED: Array<[string, number, number, string, Array<[string, number, number]>]> = [
  // the station of `stubRows`: all of the elements
  ['USW00000001', 40.7789, -73.9692, 'STUB STATION', [['TAVG', 2014, 2016], ['TMAX', 1990, 2020], ['TMIN', 1990, 2020], ['PRCP', 1990, 2020]]],
  // a long record of TAVG only, still reporting: for the temperature, and no precipitation
  ['USW00000002', 41, -73.5, 'TAVG ONLY', [['TAVG', 1950, THIS_YEAR]]],
  // TMAX and TMIN that overlap for 9 years only: no 10-year span, though each has 20
  ['USW00000003', 40.5, -74.2, 'NARROW OVERLAP', [['TMAX', 1950, 1969], ['TMIN', 1961, 1980]]],
  // TMAX alone: no mean can be made of it
  ['USW00000004', 40.6, -74.1, 'TMAX ONLY', [['TMAX', 1940, THIS_YEAR]]],
  // a long record of rain that ended in 2005, and one that is still reporting
  ['USW00000005', 40.9, -73.8, 'RAIN CLOSED', [['PRCP', 1960, 2005]]],
  ['USW00000006', 40.4, -73.1, 'RAIN OPEN', [['PRCP', 1980, THIS_YEAR]]],
  // five years: too short for either
  ['USW00000007', 40.7, -73.9, 'SHORT', [['TAVG', 2018, 2022], ['PRCP', 2018, 2022]]],
  // a long record that ended last year: still active
  ['USW00000008', 51.5, -0.1, 'LAST YEAR', [['TMAX', 1970, THIS_YEAR - 1], ['TMIN', 1970, THIS_YEAR - 1]]],
  // nine years of TMAX, TMIN and PRCP: below the minimum, so listed for no kind
  ['USW00000009', 40.8, -73.7, 'NINE YEARS', [['TMAX', 1990, 1998], ['TMIN', 1990, 1998], ['PRCP', 1990, 1998]]],
]

/**
 * What `/api/stations` gives for one daily parameter (GH-4270): the stations that have its element, with that element's span, the
 * year that runs having no end, as the listing writes it
 */
export function listOf(parameter: string) {
  return LISTED.flatMap(([id, latitude, longitude, name, elements]) => {
    const found = elements.find(([element]) => element === ELEMENT_OF[parameter])
    return found
      ? [{
          resolution: 'daily',
          dataset: 'data',
          station_id: id,
          start_timestamp: `${found[1]}-01-01T00:00:00.000000+00:00`,
          end_timestamp: found[2] < THIS_YEAR ? `${found[2]}-12-31T00:00:00.000000+00:00` : null,
          latitude,
          longitude,
          elevation: 42.7,
          name,
          region: 'NY',
          wmo_id: null,
          wigos_id: null,
          icao_id: null,
        }]
      : []
  })
}

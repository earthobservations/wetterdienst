import type { Handlers } from './mock-backend'
import { DateTime } from 'luxon'
import { defaultHandlers, STATIONS } from './mock-backend'

// What the home page's questions are answered from (components/AnswerPanel.vue), as the mock backend gives it: the
// MOSMIX point nearest the place with tomorrow's rain, the monthly means of every season, the daily wind of a fortnight,
// and a provider list whose networks have an hourly resolution. Small and fixed, shaped as `shared/types/api.ts` has
// them, and relative to the day the spec runs on, as the questions are.

export const KIEL_MOSMIX = { station_id: '10046', name: 'KIEL-HOLTENAU', region: null, latitude: 54.38, longitude: 10.15, elevation: 28, start_timestamp: null, end_timestamp: null, distance: 0.6 }

/** Every request the questions made, by path and its query, so that a spec can say what was asked and what was not */
export interface Asked {
  path: string
  query: Record<string, string>
}

function reading(station_id: string, resolution: string, dataset: string, parameter: string, timestamp: string, value: number) {
  return { station_id, resolution, dataset, parameter, timestamp, value, quality_flags: null }
}

/** The months of each season, and the first day it is over (the answer's rule): the winter has the December before it and is named for the year of its January */
export type MockSeason = 'spring' | 'summer' | 'autumn' | 'winter'
const MONTHS: Record<MockSeason, number[]> = { spring: [3, 4, 5], summer: [6, 7, 8], autumn: [9, 10, 11], winter: [12, 1, 2] }

/** The year of the last season of a kind that is over: the winter 2025/26 is named 2026 and is over on 1 March */
export function lastSeasonYear(season: MockSeason, now = DateTime.now()): number {
  const over = (year: number) => DateTime.utc(year, MONTHS[season][2]!, 1).plus({ months: 1 })
  return now >= over(now.year) ? now.year : now.year - 1
}

/** The last June to August that is over (the answer's rule: from the first of September on) */
export function lastSummerYear(now = DateTime.now()): number {
  return lastSeasonYear('summer', now)
}

export function rainValues(station: string) {
  // tomorrow in Kiel, 15:00 to 16:00 local, is a millimetre; the rest of the days is dry. Four days of hours, so that the whole of tomorrow is there
  const tomorrow = DateTime.now().setZone('Europe/Berlin').startOf('day').plus({ days: 1 })
  // the hour closing at 16:00 is the wettest, with the one before and after it
  const wet = new Map(([[15, 0.3], [16, 1.2], [17, 0.6]] as Array<[number, number]>).map(([hour, amount]) => [tomorrow.plus({ hours: hour }).toMillis(), amount]))
  const start = DateTime.now().toUTC().startOf('hour').minus({ hours: 12 })
  return Array.from({ length: 108 }, (_, hour) => start.plus({ hours: hour })).flatMap((at) => {
    const stamp = at.toISO({ suppressMilliseconds: true })!
    return [
      reading(station, 'hourly', 'large', 'precipitation_amount_significant_weather_last_1h', stamp, wet.get(at.toMillis()) ?? 0),
      reading(station, 'hourly', 'large', 'probability_precipitation_amount_gt_0_1mm_last_1h', stamp, wet.has(at.toMillis()) ? 0.85 : 0.05),
    ]
  })
}

/** The year a station's record of monthly means starts in: Arkona's starts in 1975, so that it has 16 of the 30 years of 1961 to 1990 and that normal is offered disabled */
const FIRST_YEAR: Record<string, number> = { '00183': 1975 }
const FIRST_YEAR_DEFAULT = 1961
/** Aue has only the winters from 2018/19 on, so that the season is greyed out there (8 complete winters, and 2 of the 30 of 1991-2020) */
const FIRST_WINTER: Record<string, number> = { '00205': 2019 }

/** The temperature of a season of a year: a level, a slow warming (none for the summer, which the first spec fixed), a swing, and a known last season */
function seasonMean(season: MockSeason, year: number, last: number): number {
  const level = { spring: 8.2, summer: 16.2, autumn: 9.6, winter: 1 }[season]
  if (year === last)
    return { spring: 12.3, summer: 18.1, autumn: 11.4, winter: 4.1 }[season]
  const warming = season === 'summer' ? 0 : 0.04 * (year - 1961)
  return level + warming + 1.2 * Math.sin(year * (MONTHS[season][0]! + 1))
}

/** The monthly means of a station, every month of every season of its record up to the last full month, so that every season and every normal is answered from them */
export function monthlyValues(station: string, now = DateTime.now()) {
  const firstYear = FIRST_YEAR[station] ?? FIRST_YEAR_DEFAULT
  const lastOf = Object.fromEntries((Object.keys(MONTHS) as MockSeason[]).map(season => [season, lastSeasonYear(season, now)])) as Record<MockSeason, number>
  const rows = []
  for (let year = firstYear - 1; year <= now.year; year++) {
    for (let month = 1; month <= 12; month++) {
      // a month is in the answer once it is over
      if (DateTime.utc(year, month, 1).plus({ months: 1 }) > now.toUTC())
        continue
      const season = (Object.keys(MONTHS) as MockSeason[]).find(each => MONTHS[each].includes(month))!
      const named = season === 'winter' && month === 12 ? year + 1 : year
      if (named < firstYear)
        continue
      if (season === 'winter' && named < (FIRST_WINTER[station] ?? 0))
        continue
      const value = Math.round(seasonMean(season, named, lastOf[season]) * 100) / 100
      rows.push(reading(station, 'monthly', 'climate_summary', 'temperature_air_mean_2m', `${year}-${String(month).padStart(2, '0')}-01T00:00:00+00:00`, value))
    }
  }
  return rows
}

/** The monthly means the summer question was answered from (and every other season's, now) */
export function summerValues(station: string) {
  return monthlyValues(station)
}

/** Stations of the mock that have no snow depth reading (a coastal station): the snow measure is greyed out there, with its reason */
export const WITHOUT_SNOW = new Set(['00183'])

/**
 * The daily readings of a fortnight (the day question, GH-3764): the wind, the sunshine, the precipitation, the highest and the lowest
 * temperature, the snow depth and, on two days, the fresh snow. 26 December 2025 is a stormy, dull, wet frost day with snow on the ground, 20 December
 * a calm, sunny, dry and ordinary one with none; the days between and around follow a plain curve (the one that is not either is
 * mild and dry), so that each verdict has a day to be read from.
 */
export function dayValues(station: string, range: string | null) {
  const [from, to] = (range ?? '2025-12-19/2026-01-02').split('/')
  const first = DateTime.fromISO(from!, { zone: 'utc' })
  const days = Math.round(DateTime.fromISO(to!, { zone: 'utc' }).diff(first, 'days').days)
  return Array.from({ length: days + 1 }, (_, index) => first.plus({ days: index })).flatMap((day) => {
    const stamp = `${day.toISODate()}T00:00:00+00:00`
    const stormy = day.month === 12 && day.day === 26
    const sunny = day.month === 12 && day.day === 20
    const rows = [
      reading(station, 'daily', 'climate_summary', 'wind_gust_max', stamp, stormy ? 21.6 : 5 + 2 * Math.sin(day.day)),
      reading(station, 'daily', 'climate_summary', 'wind_speed_mean', stamp, stormy ? 9.1 : 3.2 + Math.cos(day.day)),
      reading(station, 'daily', 'climate_summary', 'sunshine_duration', stamp, stormy ? 1.4 : sunny ? 5.6 : 2.5 + Math.sin(day.day)),
      reading(station, 'daily', 'climate_summary', 'precipitation_amount', stamp, stormy ? 6.4 : sunny ? 0 : Math.max(0, Math.round(2 * Math.sin(day.day) * 10) / 10)),
      reading(station, 'daily', 'climate_summary', 'temperature_air_max_2m', stamp, stormy ? 3.4 : sunny ? 7.2 : 6 + Math.sin(day.day)),
      reading(station, 'daily', 'climate_summary', 'temperature_air_min_2m', stamp, stormy ? -1.2 : sunny ? 2.1 : 2 + Math.cos(day.day)),
    ]
    if (!WITHOUT_SNOW.has(station)) {
      rows.push(reading(station, 'daily', 'climate_summary', 'snow_depth', stamp, stormy ? 4 : 0))
      // the fresh snow is a value of its own, which only some stations report: this one reports it for the stormy day
      if (stormy)
        rows.push(reading(station, 'daily', 'precipitation_more', 'snow_depth_new', stamp, 2))
    }
    return rows
  })
}

/** A backend that answers the questions; `asked` collects what they ask */
export function askHandlers(asked: Asked[] = []): Handlers {
  const base = defaultHandlers()
  const record = (path: string, url: URL) => asked.push({ path, query: Object.fromEntries(url.searchParams) })
  return {
    stations: (url, route) => {
      record('stations', url)
      // the forecast point nearest a place
      if (url.searchParams.get('network') === 'mosmix' && url.searchParams.has('latitude'))
        return { stations: [KIEL_MOSMIX] }
      return base.stations!(url, route)
    },
    values: (url) => {
      record('values', url)
      const station = url.searchParams.get('stations') ?? '02564'
      const parameters = url.searchParams.get('parameters') ?? ''
      if (url.searchParams.get('network') === 'mosmix')
        return { values: rainValues(station) }
      if (parameters.startsWith('monthly/'))
        return { values: monthlyValues(station) }
      return { values: dayValues(station, url.searchParams.get('timestamp')) }
    },
  }
}

export { STATIONS }

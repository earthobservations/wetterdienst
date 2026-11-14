/**
 * The rows of the compact overview and of the map's panel: one for each day of the forecast, with its weather, its
 * temperatures and its rain.
 */
import type { SeriesMap } from './meteogram-series'
import type { MeteogramUnits } from './meteogram-units'
import type { WeatherKind } from './weather-kind'
import { DateTime } from 'luxon'
import { formatDayMonth, formatNumber, weekdayShort } from './format'
import { METEOGRAM_SERIES } from './meteogram'
import { findFirstAvailable } from './meteogram-series'
import { withUnit } from './units'
import { weatherCodeToKind } from './weather-kind'

/** The days the compact overview lists at most, for readability */
export const MAX_COMPACT_DAYS = 7

export interface MeteogramDay {
  date: DateTime
  kind: WeatherKind
  weekday: string
  dayMonth: string
  tempLabel?: string | null
  precipLabel?: string | null
  isToday: boolean
  partialHours: number | null
}

/** How bad a WMO present-weather code is, for choosing the one a day is told by */
function weatherSeverity(code: number): number {
  if (code >= 95 && code <= 99)
    return 9 // thunderstorm
  if (code >= 80 && code <= 86)
    return 8 // showers
  if (code >= 70 && code <= 79)
    return 7 // snow
  if (code >= 60 && code <= 69)
    return 6 // rain
  if (code >= 50 && code <= 59)
    return 5 // drizzle
  if (code >= 40 && code <= 49)
    return 4 // fog
  if (code === 3)
    return 3 // overcast / cloudy
  if (code === 2)
    return 2 // partly cloudy
  if (code === 1)
    return 1 // mostly clear
  return 0 // clear / sunny / default
}

/**
 * The code a day is told by, of the codes its hours have (code to count): where a code of severity 3 or more
 * occurs at least twice, the worst of those; otherwise the most frequent. Null where there is none.
 */
export function dayWeatherCode(counts: Map<number, number>): number | null {
  let best = -1
  let highestSeverity = -1
  let mostFrequent = -1
  let maxCount = -1
  for (const [code, count] of counts) {
    if (count > maxCount) {
      mostFrequent = code
      maxCount = count
    }
    const severity = weatherSeverity(code)
    if (severity >= 3 && count >= 2 && severity > highestSeverity) {
      highestSeverity = severity
      best = code
    }
  }
  // If no significant weather with count >= 2, fall back to most frequent
  if (best === -1)
    best = mostFrequent
  return best === -1 ? null : best
}

export interface DaysContext {
  /** the station's time zone */
  zone: string
  /** the date it is today at the station, `2026-10-05` */
  today: string
  units: MeteogramUnits
  /** the app's locale code, which numbers are written in */
  locale: string
  /** the language tag dates are written in */
  language: string
}

/** One row for each day from today (the station's local day) to the end of the run, at most `MAX_COMPACT_DAYS` */
export function meteogramDays(series: SeriesMap, { zone, today: todayISO, units, locale, language }: DaysContext): MeteogramDay[] {
  const out: MeteogramDay[] = []
  const available = new Set(series.keys())
  const weatherKey = findFirstAvailable(METEOGRAM_SERIES.weather, available)
  const precipKey = findFirstAvailable(METEOGRAM_SERIES.precipitation, available)
  const tempKey = findFirstAvailable(METEOGRAM_SERIES.temperature, available)
  const cloudKey = findFirstAvailable(METEOGRAM_SERIES.cloudCover, available)

  // the start of today at the station: where the rows start, and the row that is marked as today
  const today = DateTime.fromISO(todayISO, { zone }).startOf('day')

  const allTimes = [...series.values()].flatMap(s => s.x.map(d => d.getTime()))
  if (!allTimes.length)
    return out
  const minTime = Math.min(...allTimes)
  const maxTime = Math.max(...allTimes)

  // The rows start at today (the station's local day): the run begins before midnight, and what is left of
  // the day before it is a stub of a day that is over (GH-3840)
  const first = DateTime.fromMillis(minTime, { zone }).startOf('day')
  let dt = first < today ? today : first
  const last = DateTime.fromMillis(maxTime, { zone }).startOf('day')
  // the step the run ends with, from its last two times: the run is hourly and then 3-hourly, which the span says
  // nothing of
  const times = [...new Set(allTimes)].sort((a, b) => a - b)
  const endStep = times.length > 1 ? times[times.length - 1]! - times[times.length - 2]! : 3_600_000
  while (dt.toMillis() <= last.toMillis()) {
    const startUTC = dt.toUTC().toMillis()
    const endUTC = dt.plus({ days: 1 }).toUTC().toMillis()

    // null while neither a weather code nor the fallback below has said
    let kind: WeatherKind | null = null

    // Prefer significant weather codes when available
    if (weatherKey && series.has(weatherKey)) {
      const ws = series.get(weatherKey)!
      const counts = new Map<number, number>()
      for (let i = 0; i < ws.x.length; i++) {
        const time = ws.x[i]!.getTime()
        if (time >= startUTC && time < endUTC) {
          const raw = ws.y[i]
          const code = typeof raw === 'number' ? Math.round(raw) : Number.parseInt(String(raw))
          if (!Number.isNaN(code))
            counts.set(code, (counts.get(code) ?? 0) + 1)
        }
      }
      const best = dayWeatherCode(counts)
      if (best !== null)
        kind = weatherCodeToKind(best)
    }

    let minT = Number.POSITIVE_INFINITY
    let maxT = Number.NEGATIVE_INFINITY
    if (tempKey && series.has(tempKey)) {
      const ts = series.get(tempKey)!
      for (let i = 0; i < ts.x.length; i++) {
        const time = ts.x[i]!.getTime()
        if (time >= startUTC && time < endUTC) {
          const val = Number(ts.y[i] ?? Number.NaN)
          if (!Number.isNaN(val)) {
            minT = Math.min(minT, val)
            maxT = Math.max(maxT, val)
          }
        }
      }
    }

    // Precipitation total for the day (always computed)
    let dayPrecip = 0
    if (precipKey && series.has(precipKey)) {
      const ps = series.get(precipKey)!
      for (let i = 0; i < ps.x.length; i++) {
        const time = ps.x[i]!.getTime()
        if (time >= startUTC && time < endUTC)
          dayPrecip += Number(ps.y[i] ?? 0)
      }
    }

    // Fallback heuristics: cloud cover
    if (kind === null) {
      let cloudSum = 0
      let cloudCount = 0
      if (cloudKey && series.has(cloudKey)) {
        const cs = series.get(cloudKey)!
        for (let i = 0; i < cs.x.length; i++) {
          const time = cs.x[i]!.getTime()
          if (time >= startUTC && time < endUTC) {
            // in percent whatever the unit the cloud cover is shown in: the thresholds below are percentages
            cloudSum += units.canon('fraction', cs.y[i] ?? 0)
            cloudCount++
          }
        }
      }
      const avgCloud = cloudCount ? (cloudSum / cloudCount) : 0
      // judged in millimetres and degrees Celsius, whatever the units the day is shown in (GH-3980)
      if (units.canon('precipitation', dayPrecip) > 0.5)
        kind = (Number.isFinite(minT) && units.canon('temperature', minT) <= 0.5) ? 'snow' : 'rain'
      else if (avgCloud >= 70)
        kind = 'cloudy'
      else if (avgCloud >= 30)
        kind = 'partlyCloudy'
      else
        kind = 'clear'
    }

    const tempLabel = Number.isFinite(minT) && Number.isFinite(maxT) ? withUnit(`${Math.round(minT)} / ${Math.round(maxT)}`, units.unitOf('temperature')) : null
    const precipLabel = units.canon('precipitation', dayPrecip) >= 0.1 ? withUnit(formatNumber(dayPrecip, locale, 1), units.unitOf('precipitation')) : null
    const isToday = dt.hasSame(today, 'day')
    // The last day of the run, when the run ends before it does: its minimum and maximum are those of the hours
    // the run reaches, so the row says how many they are, and is not read as a day's own
    let partialHours: number | null = null
    if (dt.toMillis() === last.toMillis() && maxTime + endStep < endUTC)
      partialHours = Math.max(1, Math.round((maxTime + endStep - Math.max(startUTC, minTime)) / 3_600_000))
    out.push({ date: dt, kind, weekday: weekdayShort(dt, language), dayMonth: formatDayMonth(dt, language), tempLabel, precipLabel, isToday, partialHours })
    dt = dt.plus({ days: 1 })
  }
  // Limit number of days shown in compact mode for readability
  return out.length > MAX_COMPACT_DAYS ? out.slice(0, MAX_COMPACT_DAYS) : out
}

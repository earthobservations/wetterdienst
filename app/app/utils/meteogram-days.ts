/**
 * The rows of the compact overview and of the map's panel: one for each day of the forecast, with its weather, its
 * temperatures and its rain.
 */
import type { SeriesMap } from './meteogram-series'
import type { MeteogramUnits } from './meteogram-units'
import type { WeatherKind } from './weather-kind'
import type { Sky } from './weather-symbols'
import { DateTime } from 'luxon'
import { formatDayMonth, formatNumber, weekdayShort } from './format'
import { classifyPrecip, METEOGRAM_SERIES, wetBulbApprox } from './meteogram'
import { HOUR_MS } from './meteogram-geometry'
import { planPrecipitation, precipitationOver } from './meteogram-precipitation'
import { findFirstAvailable } from './meteogram-series'
import { withUnit } from './units'
import { skyOfCloudCover, weatherCodeToKind } from './weather-kind'

/** A day the run reaches fewer hours of than this is marked partial, with the hours it has */
const PARTIAL_BELOW_HOURS = 20

export interface MeteogramDay {
  date: DateTime
  kind: WeatherKind
  /** the sky of the day from its mean cloud cover (`skyOfCloudCover`), which the symbol of wind, dust and a funnel cloud takes (GH-4193) */
  sky: Sky
  /** the rain of the day in millimetres, whatever unit the label is written in; null where the forecast has none. What the rain of 0.5 mm rule judges (GH-4175) */
  precipitationMm: number | null
  /**
   * The rate of the day's wettest hour in millimetres an hour, whatever unit the label is written in (for a late day made of 6, 12 or 24 hour
   * totals, the rate of its wettest block: the amount over its hours); null where the forecast has none. What the strength of the symbol is
   * told by, as the chart's hours are (GH-4193): 4 mm an hour is heavy rain and 2 mm an hour heavy snow, and a day of drizzle is not heavy
   * by its total.
   */
  precipitationPeakMm: number | null
  weekday: string
  dayMonth: string
  tempLabel?: string | null
  /**
   * The rain of the day with its unit. `≈` before it: it is made of totals of more than one hour (6, 12 or 24), which a local day cuts
   * evenly where a block crosses its midnight. `≥` before it: some hours of the day have no amount, which are not 0, so it is the least
   * the forecast says. Null under 0.1 mm.
   */
  precipLabel?: string | null
  /** the hours of the longest block the rain of the day is made of, where it is more than an hour (the label has `≈`), else null */
  precipBlockHours: number | null
  /** the hours of the day, between the first and the last the forecast has an amount for, that it has none for (the label has `≥`) */
  precipMissingHours: number
  isToday: boolean
  /**
   * The hours of the day the forecast reaches, where it is less than 20 of them: the first day starts at the first hour after the
   * run's issue, the last ends with the run (the minimum, maximum and rain are those of the hours it has). Null for a day it has 20 or
   * more hours of.
   */
  partialHours: number | null
}

/** How bad a WMO present-weather code is, for choosing the one a day is told by (0 for the codes that name no weather) */
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
  // 0 to 3 are DWD's cloud development (none, dissolving, unchanged, forming): no weather, and no sky (GH-4190)
  return 0
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

/** One row for each day from today (the station's local day) to the end of the run: every day the forecast has (GH-4127) */
export function meteogramDays(series: SeriesMap, { zone, today: todayISO, units, locale, language }: DaysContext): MeteogramDay[] {
  const out: MeteogramDay[] = []
  const available = new Set(series.keys())
  const weatherKey = findFirstAvailable(METEOGRAM_SERIES.weather, available)
  const tempKey = findFirstAvailable(METEOGRAM_SERIES.temperature, available)
  const humidityKey = findFirstAvailable(METEOGRAM_SERIES.humidity, available)
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
  // the rain of the run, as the blocks of 1, 6, 12 or 24 hours that account for MOSMIX's totals (`planPrecipitation`)
  const plan = planPrecipitation(series, amount => units.canon('precipitation', amount))
  while (dt.toMillis() <= last.toMillis()) {
    const startUTC = dt.toUTC().toMillis()
    const endUTC = dt.plus({ days: 1 }).toUTC().toMillis()

    // null while no weather code that names weather has said; the sky of the day is then the cloud cover's, below
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
    let sumT = 0
    let countT = 0
    const humidity = humidityKey ? series.get(humidityKey) : undefined
    const humidityAt = humidity ? new Map(humidity.x.map((d, i) => [d.getTime(), humidity.y[i]!])) : undefined
    if (tempKey && series.has(tempKey)) {
      const ts = series.get(tempKey)!
      for (let i = 0; i < ts.x.length; i++) {
        const time = ts.x[i]!.getTime()
        if (time >= startUTC && time < endUTC) {
          const val = Number(ts.y[i] ?? Number.NaN)
          if (!Number.isNaN(val)) {
            minT = Math.min(minT, val)
            maxT = Math.max(maxT, val)
            // the wet bulb of the hour as the panel judges its blocks by: with the humidity where the forecast has it, else the air's
            const rh = humidityAt?.get(time)
            const celsius = units.canon('temperature', val)
            sumT += rh === undefined ? celsius : wetBulbApprox(celsius, units.canon('fraction', rh))
            countT++
          }
        }
      }
    }

    // The rain of the day: each block adds the share of its hours that are in the day, and an hour with no amount adds nothing (it is
    // not a 0: `precipMissingHours` counts them)
    const over = plan ? precipitationOver(plan, startUTC, endUTC) : null
    const dayPrecip = over?.amount ?? null

    // The sky of the day by its mean cloud cover, by the thresholds of the chart's hours: the sky of a day no weather code names weather for
    // (the codes 0 to 3 name none), and what the symbol of wind, dust and a funnel cloud is drawn from (GH-4193)
    let cloudSum = 0
    let cloudCount = 0
    if (cloudKey && series.has(cloudKey)) {
      const cs = series.get(cloudKey)!
      for (let i = 0; i < cs.x.length; i++) {
        const time = cs.x[i]!.getTime()
        if (time >= startUTC && time < endUTC) {
          // in percent whatever the unit the cloud cover is shown in: the thresholds of the sky are percentages
          cloudSum += units.canon('fraction', cs.y[i] ?? 0)
          cloudCount++
        }
      }
    }
    const sky = skyOfCloudCover(cloudCount ? (cloudSum / cloudCount) : null)
    if (kind === null)
      kind = sky

    // A day whose rain is 0.5 mm or more is a day of rain, which its weather codes (those of 0 to 3 name none, and they are dry in the tail of a
    // run, where the hourly amount is 0.0 and the totals of 6, 12 or 24 hours carry the rain) do not say: the icon follows the amount (as the label writes it: a day of 0.45 mm reads 0.5), as
    // snow or sleet where the mean wet bulb of the day's hours is as cold as it is for the blocks of the panel (GH-4175)
    if (dayPrecip !== null && units.canon('precipitation', Number(formatNumber(dayPrecip, 'en', 1).replaceAll(',', ''))) >= 0.5 && (kind === 'clear' || kind === 'partlyCloudy' || kind === 'cloudy')) {
      const phase = countT ? classifyPrecip(sumT / countT) : 'rain'
      kind = phase === 'snow' ? 'snow' : phase === 'mixed' ? 'sleet' : 'rain'
    }

    const tempLabel = Number.isFinite(minT) && Number.isFinite(maxT) ? withUnit(`${Math.round(minT)} / ${Math.round(maxT)}`, units.unitOf('temperature')) : null
    const precipBlockHours = over && over.longest > 1 ? over.longest : null
    // the hours the hourly series reaches that the plan has no block for are missing too: where the plan goes to 6 or 12 hour totals it ends
    // with the last of them (4 h before the run does), and the day it ends in has the rain of fewer hours than the temperatures of
    const planEnd = plan ? plan.blocks[plan.blocks.length - 1]!.end : 0
    const beyondPlan = over && over.given > 0 ? Math.max(0, Math.min(endUTC, maxTime) - Math.max(startUTC, planEnd)) / HOUR_MS : 0
    const precipMissingHours = Math.round((over?.missing ?? 0) + beyondPlan)
    // a label of a figure that is not the whole day's own: the least it says, or made of totals of more than an hour
    const precipMark = precipMissingHours > 0 ? '≥' : precipBlockHours !== null ? '≈' : ''
    const precipLabel = dayPrecip !== null && units.canon('precipitation', dayPrecip) >= 0.1 ? `${precipMark}${withUnit(formatNumber(dayPrecip, locale, 1), units.unitOf('precipitation'))}` : null
    const isToday = dt.hasSame(today, 'day')
    // A day the run does not reach all of, at its start (the first hour of the run is the one after its issue) or its end: its
    // minimum, maximum and rain are those of the hours the run reaches, so the row says how many they are, and is not read as a day's own
    // A day with 20 or more of its hours is not marked: the note is for a stub of a day, not for four hours missing at an end (GH-4175)
    let partialHours: number | null = null
    if (startUTC < minTime || maxTime + HOUR_MS < endUTC) {
      const hours = Math.max(1, Math.round((Math.min(endUTC, maxTime + HOUR_MS) - Math.max(startUTC, minTime)) / HOUR_MS))
      partialHours = hours < PARTIAL_BELOW_HOURS ? hours : null
    }
    out.push({ date: dt, kind, sky, precipitationMm: dayPrecip === null ? null : units.canon('precipitation', dayPrecip), precipitationPeakMm: over?.peak == null ? null : units.canon('precipitation', over.peak), weekday: weekdayShort(dt, language), dayMonth: formatDayMonth(dt, language), tempLabel, precipLabel, precipBlockHours, precipMissingHours, isToday, partialHours })
    dt = dt.plus({ days: 1 })
  }
  return out
}

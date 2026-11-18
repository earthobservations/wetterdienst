import type { MeteogramDay } from '../../app/utils/meteogram-days'
import { describe, expect, it } from 'vitest'
import { meteogramDays } from '../../app/utils/meteogram-days'
import { buildSeries } from '../../app/utils/meteogram-series'
import { meteogramUnits } from '../../app/utils/meteogram-units'
import { FORECAST_UNITS, forecastValues } from '../helpers/meteogram-forecast'
import { PRECIPITATION, run10382Values } from '../helpers/mosmix-run'

// The rows of the compact overview and of the map's panel: one for each day of the forecast, with its rain (GH-4175)

const HOUR = 3_600_000
const t = (key: string) => key
const units = meteogramUnits(FORECAST_UNITS, t)

function days(values: unknown[], context: { zone?: string, today: string }): MeteogramDay[] {
  return meteogramDays(buildSeries(values as any), { zone: 'Europe/Berlin', units, locale: 'en', language: 'en-GB', ...context })
}
const byDate = (rows: MeteogramDay[]) => Object.fromEntries(rows.map(row => [row.date.toISODate()!, row]))

describe('the rain of the days of a run whose hourly amount is 0.0 late in it (10382, 2026-11-17 03 UTC)', () => {
  const run = days(run10382Values(), { today: '2026-11-17' })
  const rows = byDate(run)

  it('has a row for every day to the end of the run', () => {
    expect(run.map(row => row.date.toISODate())).toEqual(['2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22', '2026-11-23', '2026-11-24', '2026-11-25', '2026-11-26', '2026-11-27'])
  })

  it('shows the first days from the hourly amounts, with no mark: their sums are DWD\'s own', () => {
    expect(rows['2026-11-18']!.precipLabel).toBe('6.8 mm')
    expect(rows['2026-11-19']!.precipLabel).toBe('8.7 mm')
    expect(rows['2026-11-18']!.precipBlockHours).toBeNull()
  })

  it('shows the late days from the 6 and 12 hour totals, where the hourly amounts say 0.0, and marks them as approximate', () => {
    // the hourly amounts of 2026-11-24 to 26 are all 0.0 (a dry label); DWD's totals have 0.5, 1.2 and 1.1 mm
    const hourly = days(run10382Values({ without: [PRECIPITATION.six, PRECIPITATION.twelve, PRECIPITATION.day] }), { today: '2026-11-17' })
    for (const date of ['2026-11-24', '2026-11-25', '2026-11-26'])
      expect(byDate(hourly)[date]!.precipLabel, `${date} from the hourly amounts`).toBeNull()
    expect(rows['2026-11-24']).toMatchObject({ precipLabel: '≈0.5 mm', precipBlockHours: 12 })
    expect(rows['2026-11-25']).toMatchObject({ precipLabel: '≈1.2 mm', precipBlockHours: 12 })
    expect(rows['2026-11-26']).toMatchObject({ precipLabel: '≈1.1 mm', precipBlockHours: 12 })
    // a day whose totals have no rain has none of it either
    expect(rows['2026-11-23']!.precipLabel).toBeNull()
  })

  it('has the last day say its rain covers fewer hours than the run does: the totals end 4 hours before the run, and the figure is the least', () => {
    // the 12 hour totals end at 06:00 UTC on the 27th, the temperatures at 10:00: 4 hours of the day the rain has no amount for
    expect(run.slice(0, -1).map(row => row.precipMissingHours)).toEqual(Array.from({ length: 10 }).fill(0))
    expect(run.at(-1)!.precipMissingHours).toBe(4)
    expect(run.at(-1)!.precipLabel).toMatch(/^≥/)
    // and no other day is marked as the least
    expect(run.slice(0, -1).some(row => row.precipLabel?.startsWith('≥'))).toBe(false)
  })

  it('marks the first day, which starts at the first hour after the issue, and the last, which the run ends in, as partial, as they have fewer than 20 hours', () => {
    // the first hour of the run is the one that ends at 04:00 UTC, 05:00 at Berlin; the day began at 00:00: 19 of its hours are the run's
    expect(run[0]).toMatchObject({ partialHours: 19, isToday: true })
    // the last stamp is 10:00 UTC on the 27th, 11:00 at Berlin: hours 00:00 to 11:00
    expect(run.at(-1)!.partialHours).toBe(12)
    expect(run.slice(1, -1).map(row => row.partialHours)).toEqual(Array.from({ length: 9 }).fill(null))
  })

  it('does not mark a day it has 20 hours of: a run issued an hour earlier has a first day of 20 hours, and none is partial there', () => {
    const earlier = days(run10382Values({ shiftHours: -1 }), { today: '2026-11-17' })
    expect(earlier[0]!.partialHours).toBeNull()
    // the last day has 11 hours
    expect(earlier.at(-1)!.partialHours).toBe(11)
  })

  it('draws the icon of a day of rain where its rain is the 6, 12 or 24 hour totals\' and 0.5 mm or more, and the codes of the tail say it is dry', () => {
    // 2026-11-25 (1.2 mm from the 12 hour totals) and 2026-11-24 (0.5 mm), where the hourly ww codes are 2 and 3: the icon says cloud
    // without the totals, and rain with them
    const hourlyOnly = byDate(days(run10382Values({ without: [PRECIPITATION.six, PRECIPITATION.twelve, PRECIPITATION.day] }), { today: '2026-11-17' }))
    expect(hourlyOnly['2026-11-25']!.kind).toBe('cloudy')
    expect(rows['2026-11-25']!.kind).toBe('rain')
    expect(rows['2026-11-26']!.kind).toBe('rain')
    // a day of 0.45 mm reads 0.5 in its label, which is what the threshold is judged on: the icon agrees with the label
    expect(rows['2026-11-24']!.precipLabel).toBe('≈0.5 mm')
    // (a day of a mean of 1 degree, which is sleet by the panel's thresholds)
    expect(rows['2026-11-24']!.kind).toBe('sleet')
    // a day under 0.5 mm of the totals keeps its sky (0.0 mm on the 23rd): by its cloud cover, a mean of 69.7 %, not by its codes 2 and 3,
    // DWD's cloud development (GH-4190)
    expect(rows['2026-11-23']!.kind).toBe('partlyCloudy')
    // a day of the hourly amounts, whose hours are all rain (code 61), is rain with the totals and without them
    expect(rows['2026-11-18']!.kind).toBe('rain')
    expect(hourlyOnly['2026-11-18']!.kind).toBe('rain')
  })

  it('draws snow where the mean wet bulb of the day\'s hours is as cold as the panel\'s snow, which the humidity lowers below the air\'s', () => {
    const colder = (degrees: number) => run10382Values().map(value => value.parameter === 'temperature_air_2m' ? { ...value, value: value.value! - 7 + degrees } : value)
    expect(byDate(days(colder(-4), { today: '2026-11-17' }))['2026-11-25']!.kind).toBe('snow')
    // an air of 1.5 degrees is sleet by itself (the panel's thresholds are 0.5 and 2), and snow where the air is dry: the wet bulb at 40 % is below 0.5
    const constant = run10382Values().map(value => value.parameter === 'temperature_air_2m' ? { ...value, value: 1.5 } : value)
    const dry = [...constant, ...constant.filter(value => value.parameter === 'temperature_air_2m').map(value => ({ ...value, parameter: 'humidity_relative', value: 40 }))]
    expect(byDate(days(constant, { today: '2026-11-17' }))['2026-11-25']!.kind).toBe('sleet')
    expect(byDate(days(dry, { today: '2026-11-17' }))['2026-11-25']!.kind).toBe('snow')
  })
})

describe('the rain over a local day made of 6 hour blocks', () => {
  // MOSMIX's 6 hour totals only: 1 mm in each block of 6 hours from 2026-10-24 00 UTC to 2026-10-27, whatever the weather
  const origin = Date.UTC(2026, 9, 24, 0)
  const sixHourly = Array.from({ length: 12 }, (_, i) => ({
    station_id: '10382',
    resolution: 'hourly',
    dataset: 'large',
    parameter: PRECIPITATION.six,
    timestamp: new Date(origin + 6 * (i + 1) * HOUR).toISOString(),
    value: 1,
    quality_flags: null,
  }))
  const hours = (n: number) => `${((n / 6) * 10 / 10).toFixed(1)} mm`

  it('is the share of each block that is in the day, the day of 25 hours at the autumn change of the clock having 25 of them', () => {
    // 2026-10-25 at Berlin is 25 hours (the clocks go back at 03:00): 25 of the 6-hour blocks' hours, 25/6 mm
    const rows = byDate(days(sixHourly, { today: '2026-10-24' }))
    expect(rows['2026-10-25']!.precipLabel).toBe(`≈${hours(25)}`)
    expect(rows['2026-10-25']!.precipBlockHours).toBe(6)
    // a day that the blocks do not all cover (the 24th starts before the first block) is not the whole of its rain: it has its part of it,
    // which the row says by the day's partial hours
    expect(rows['2026-10-24']!.partialHours).not.toBeNull()
  })

  it('is the share of the day of 23 hours at the spring change of the clock', () => {
    const springOrigin = Date.UTC(2026, 2, 28, 0)
    const spring = sixHourly.map((value, i) => ({ ...value, timestamp: new Date(springOrigin + 6 * (i + 1) * HOUR).toISOString() }))
    const rows = byDate(days(spring, { today: '2026-03-28' }))
    expect(rows['2026-03-29']!.precipLabel).toBe(`≈${hours(23)}`)
  })

  it('writes no figure for a day that is less than 0.1 mm', () => {
    const faint = sixHourly.map(value => ({ ...value, value: 0.01 }))
    expect(byDate(days(faint, { today: '2026-10-24' }))['2026-10-25']!.precipLabel).toBeNull()
  })
})

describe('the rain of a day when hours are missing', () => {
  const hourly = forecastValues({ hours: 96, without: [PRECIPITATION.six, PRECIPITATION.twelve, PRECIPITATION.day] })
  const stamp = (value: { timestamp: string }) => new Date(value.timestamp).getTime()
  const first = stamp(hourly[0]!)

  /** The amounts of the hours of a UTC day: each is the hour before its stamp, so the day's are the stamps after its midnight to the next */
  const hourlyOver = (values: typeof hourly, day: number) => values
    .filter(value => value.parameter === PRECIPITATION.hour && stamp(value) > Date.UTC(2026, 9, day) && stamp(value) <= Date.UTC(2026, 9, day + 1))
    .map(value => value.value!)

  it('adds up the hours of the day, each the hour before its stamp, with no mark where none is missing', () => {
    const rows = byDate(days(hourly, { zone: 'UTC', today: '2026-10-01' }))
    // the fixture's rain is 0.3 to 2.6 mm an hour in the hours that end at 40:00 to 49:00 of the run, 0.8 for four hours that end at 67:00 to 70:00
    const second = hourlyOver(hourly, 2)
    expect(second).toHaveLength(24)
    expect(rows['2026-10-02']!.precipLabel).toBe(`${second.reduce((sum, v) => sum + v, 0).toFixed(1)} mm`)
    expect(rows['2026-10-03']!.precipLabel).toBe(`${hourlyOver(hourly, 3).reduce((sum, v) => sum + v, 0).toFixed(1)} mm`)
    expect(rows['2026-10-02']!.precipMissingHours).toBe(0)
  })

  it('is no 0 for an hour with no amount: the figure is the least the forecast says, and says so', () => {
    // the hours that end at 44:00 and 45:00 of the run have no amount
    const missing = new Set([44, 45])
    const holed = hourly.filter(value => !(value.parameter === PRECIPITATION.hour && missing.has((stamp(value) - first) / HOUR)))
    const row = byDate(days(holed, { zone: 'UTC', today: '2026-10-01' }))['2026-10-02']!
    expect(row.precipMissingHours).toBe(2)
    expect(row.precipLabel).toMatch(/^≥/)
    // the rain of the two hours is not in it, and they are no 0 either: the sum of the 22 hours the forecast has
    const have = hourlyOver(holed, 2)
    expect(have).toHaveLength(22)
    expect(row.precipLabel).toBe(`≥${have.reduce((sum, v) => sum + v, 0).toFixed(1)} mm`)
  })

  it('has the weather of the day not made rain by a figure that is missing: a day with no amount at all has no label and keeps its sky', () => {
    const noRain = hourly.filter(value => value.parameter !== PRECIPITATION.hour && value.parameter !== 'weather_significant')
    const rows = byDate(days(noRain, { zone: 'UTC', today: '2026-10-01' }))
    expect(rows['2026-10-02']!.precipLabel).toBeNull()
    expect(rows['2026-10-02']!.kind).not.toBe('rain')
  })

  it('says how many hours of the first and the last day the run has, and none of the whole days between', () => {
    const rows = days(hourly, { today: '2026-10-01' })
    // the run starts at 00:00 UTC, which is 02:00 at Berlin: the day has 22 of its hours, which is 20 or more and no stub; it ends at
    // 00:00 UTC on the 5th, 02:00 there, 3 hours of a day of its own
    expect(rows[0]!.partialHours).toBeNull()
    expect(rows.at(-1)!.partialHours).toBe(3)
    expect(rows.slice(1, -1).every(row => row.partialHours === null)).toBe(true)
  })
})

describe('the sky of a day whose codes are DWD\'s cloud development 0 to 3 (GH-4190)', () => {
  const zone = 'Europe/Berlin'
  /** The hours of 2026-11-20 at the station (CET, one hour ahead of UTC), `hour` to its ww code and its total cloud cover */
  const day = (hours: Record<number, [number, number]>, extra: unknown[] = []) => {
    const stamp = (hour: number) => new Date(Date.UTC(2026, 10, 20, hour - 1)).toISOString().replace('.000Z', '+00:00')
    return [
      ...Object.entries(hours).flatMap(([hour, [code, cover]]) => [
        { station_id: 'C720', resolution: 'hourly', dataset: 'large', parameter: 'weather_significant', timestamp: stamp(Number(hour)), value: code, quality_flags: null },
        { station_id: 'C720', resolution: 'hourly', dataset: 'large', parameter: 'cloud_cover_total', timestamp: stamp(Number(hour)), value: cover, quality_flags: null },
      ]),
      ...extra,
    ]
  }
  const kindOf = (values: unknown[]) => byDate(days(values, { zone, today: '2026-11-20' }))['2026-11-20']!.kind

  // Hamburg-Neuwiedenthal (C720), Friday 20.11.: ww 3 at 62-74 %, 2 at 57-63 %, 1 at 56-57 %, MOSMIX run of 2026-11-17. The most frequent
  // code is 3, which DWD names clouds forming: no cover of the sky. The chart draws the hours as partly cloudy, and so does the card.
  const friday: Record<number, [number, number]> = {}
  const threes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 23]
  const covers3 = [74, 74, 73, 72, 71, 70, 69, 68, 66, 65, 64, 63, 62, 66]
  threes.forEach((hour, i) => friday[hour] = [3, covers3[i]!])
  ;[13, 14, 15, 16, 17, 20, 21, 22].forEach((hour, i) => friday[hour] = [2, [63, 62, 61, 60, 59, 58, 58, 57][i]!])
  ;[18, 19].forEach(hour => friday[hour] = [1, 56])

  it('is partly cloudy for the Friday of C720, whose most frequent code is 3 and whose cloud cover is 56 to 74 %', () => {
    const covers = Object.values(friday).map(([, cover]) => cover)
    expect(covers.reduce((sum, v) => sum + v, 0) / covers.length).toBeGreaterThan(60)
    expect(covers.reduce((sum, v) => sum + v, 0) / covers.length).toBeLessThan(70)
    expect(kindOf(day(friday))).toBe('partlyCloudy')
  })

  it('is cloudy for a day of only the codes 0 to 3 whose cloud cover is high, and clear where it is low', () => {
    const codes = [0, 1, 2, 3]
    const of = (cover: number) => Object.fromEntries(Array.from({ length: 24 }, (_, hour) => [hour, [codes[hour % 4]!, cover] as [number, number]]))
    expect(kindOf(day(of(92)))).toBe('cloudy')
    expect(kindOf(day(of(70)))).toBe('cloudy')
    expect(kindOf(day(of(45)))).toBe('partlyCloudy')
    expect(kindOf(day(of(10)))).toBe('clear')
  })

  it('has a day of code 0 and a cover of 100 % cloudy, and a day of code 3 and a cover of 0 % clear: the code says nothing of the sky', () => {
    expect(kindOf(day(Object.fromEntries(Array.from({ length: 24 }, (_, hour) => [hour, [0, 100] as [number, number]]))))).toBe('cloudy')
    expect(kindOf(day(Object.fromEntries(Array.from({ length: 24 }, (_, hour) => [hour, [3, 0] as [number, number]]))))).toBe('clear')
  })

  it('is partly cloudy for a day of the codes 0 to 3 that has no cloud cover, as the chart\'s hours are', () => {
    const values = day(friday).filter(value => (value as { parameter: string }).parameter === 'weather_significant')
    expect(kindOf(values)).toBe('partlyCloudy')
  })

  it('is still rain for a day of rain codes, whatever its cloud cover', () => {
    const rain = Object.fromEntries(Array.from({ length: 24 }, (_, hour) => [hour, [hour < 10 ? 3 : 61, 30] as [number, number]]))
    expect(kindOf(day(rain))).toBe('rain')
  })

  it('keeps the phenomenon of a day by severity, where the codes 0 to 3 are more frequent', () => {
    const thunder = Object.fromEntries(Array.from({ length: 24 }, (_, hour) => [hour, [hour >= 14 && hour < 16 ? 95 : 3, 90] as [number, number]]))
    expect(kindOf(day(thunder))).toBe('thunderstorm')
  })

  it('is rain for a day of the codes 0 to 3 whose rain amounts add up to 0.5 mm or more', () => {
    const rain = Array.from({ length: 24 }, (_, hour) => ({ station_id: 'C720', resolution: 'hourly', dataset: 'large', parameter: PRECIPITATION.hour, timestamp: new Date(Date.UTC(2026, 10, 20, hour - 1)).toISOString().replace('.000Z', '+00:00'), value: 0.3, quality_flags: null }))
    const cloudy = Object.fromEntries(Array.from({ length: 24 }, (_, hour) => [hour, [3, 90] as [number, number]]))
    expect(kindOf(day(cloudy, rain))).toBe('rain')
  })
})

// What a day card draws its Yr symbol from (GH-4193): the sky of the day's cloud cover for wind, dust and a funnel cloud, and its rain in mm
describe('the sky and the rain of a day, which its symbol is chosen by', () => {
  const stamp = (hour: number) => new Date(Date.UTC(2026, 10, 20, hour - 1)).toISOString().replace('.000Z', '+00:00')
  const hourly = (parameter: string, value: number) => Array.from({ length: 24 }, (_, hour) => ({ station_id: 'C720', resolution: 'hourly', dataset: 'large', parameter, timestamp: stamp(hour), value, quality_flags: null }))
  const dayOf = (code: number, cover: number | null, rain: number | null) => byDate(days([
    ...hourly('weather_significant', code),
    ...hourly('temperature_air_2m', 10),
    ...(cover === null ? [] : hourly('cloud_cover_total', cover)),
    ...(rain === null ? [] : hourly(PRECIPITATION.hour, rain)),
  ], { today: '2026-11-20' }))['2026-11-20']!

  it('has the sky of the cloud cover, by the chart\'s thresholds, whatever the weather the code names', () => {
    expect(dayOf(61, 10, null)).toMatchObject({ kind: 'rain', sky: 'clear' })
    expect(dayOf(61, 50, null)).toMatchObject({ kind: 'rain', sky: 'partlyCloudy' })
    expect(dayOf(18, 70, null)).toMatchObject({ kind: 'wind', sky: 'cloudy' })
    expect(dayOf(33, 20, null)).toMatchObject({ kind: 'dust', sky: 'clear' })
    expect(dayOf(19, 95, null)).toMatchObject({ kind: 'funnelCloud', sky: 'cloudy' })
  })

  it('has a partly cloudy sky where the day has no cloud cover, as the chart\'s hours do', () => {
    expect(dayOf(18, null, null).sky).toBe('partlyCloudy')
  })

  it('has the rain of the day in millimetres, and none where the forecast has no amount', () => {
    expect(dayOf(61, 50, 0.25).precipitationMm).toBeCloseTo(5.75, 5)
    expect(dayOf(61, 50, 0).precipitationMm).toBe(0)
    expect(dayOf(61, 50, null).precipitationMm).toBeNull()
  })
})

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

  it('has no rain figure that a missing hour makes smaller: no day of the run has an hour left out', () => {
    expect(run.map(row => row.precipMissingHours)).toEqual(Array.from({ length: 11 }).fill(0))
  })

  it('marks the first day, which starts at the first hour after the issue, and the last, which the run ends in, as partial', () => {
    // the first hour of the run is the one that ends at 04:00 UTC, 05:00 at Berlin; the day began at 00:00: 19 of its hours are the run's
    expect(run[0]).toMatchObject({ partialHours: 19, isToday: true })
    // the last stamp is 10:00 UTC on the 27th, 11:00 at Berlin: hours 00:00 to 11:00
    expect(run.at(-1)!.partialHours).toBe(12)
    expect(run.slice(1, -1).map(row => row.partialHours)).toEqual(Array.from({ length: 9 }).fill(null))
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
    // the run starts at 00:00 UTC, which is 02:00 at Berlin: the day has 22 of its hours; it ends at 00:00 UTC on the 5th, 02:00 there
    expect(rows[0]!.partialHours).toBe(22)
    expect(rows.at(-1)!.partialHours).toBe(3)
    expect(rows.slice(1, -1).every(row => row.partialHours === null)).toBe(true)
  })
})

import type { Series, SeriesMap } from '../../app/utils/meteogram-series'
import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import { AGREE_ROUNDING_MM, AGREE_SHARE, planPrecipitation, precipitationOver, precipitationTotal, TRACE_MM } from '../../app/utils/meteogram-precipitation'
import { buildSeries } from '../../app/utils/meteogram-series'
import { PRECIPITATION, precipitationRunKeys, precipitationRunValues } from '../helpers/mosmix-run'

const HOUR = 3_600_000

// The rain of a MOSMIX forecast as blocks of 1, 6, 12 or 24 hours (GH-4175). The runs are real: DWD's MOSMIX-L of 2026-11-16 09 and 15 UTC
// and 2026-11-17 03 UTC at 10382 (Berlin-Tegel), 10147 (Hamburg-Fuhlsbuettel), P0489 and 10961 (the Zugspitze), taken on 2026-11-17. From about
// +100 hours into a run the hourly amount (`RR1c`) is 0.0 at the lowland stations while the 6, 12 and 24 hour totals (`RR6c`, `RRhc`,
// `RRdc`) still carry rain; on the Zugspitze it carries rain to the end.

const seriesOf = (key: string): SeriesMap => buildSeries(precipitationRunValues(key) as any)
/** The instant `hours` after 2026-11-17 00 UTC, the origin of every number of hours below, whatever the run's own issue */
const T = (hours: number) => Date.UTC(2026, 10, 17, 0) + hours * HOUR

/** A series of `[hours since 2026-11-17 00 UTC, amount]` pairs */
function steps(pairs: [number, number][]): Series {
  return { x: pairs.map(([hours]) => new Date(T(hours))), y: pairs.map(([, amount]) => amount) }
}
const hourlyFrom = (first: number, amounts: number[]): [number, number][] => amounts.map((amount, i) => [first + i, amount])
const zeros = (count: number) => Array.from<number>({ length: count }).fill(0)

describe('the runs the late days were found dry in', () => {
  const keys = precipitationRunKeys()

  it('has twelve runs of four stations', () => {
    expect(keys).toHaveLength(12)
  })

  // the 24 hour windows whose first hour the run gives: each is the window of one `RRdc`
  const windowsOf = (key: string) => {
    const series = seriesOf(key)
    const day = series.get(PRECIPITATION.day)!
    const first = series.get(PRECIPITATION.hour)!.x[0]!.getTime() - HOUR
    return day.x.flatMap((end, i) => end.getTime() - 24 * HOUR >= first ? [{ start: end.getTime() - 24 * HOUR, end: end.getTime(), total: day.y[i]! }] : [])
  }
  const hourlySum = (key: string, start: number, end: number) => {
    const hour = seriesOf(key).get(PRECIPITATION.hour)!
    return hour.x.reduce((sum, d, i) => d.getTime() > start && d.getTime() <= end ? sum + hour.y[i]! : sum, 0)
  }
  const tolerance24 = (total: number) => AGREE_ROUNDING_MM * Math.sqrt(25) + AGREE_SHARE * total

  it('has windows where the hourly amounts fall short of DWD\'s 24 hour total by more than rounding, in half of those of the twelve runs', () => {
    let windows = 0
    let short = 0
    for (const key of keys) {
      for (const { start, end, total } of windowsOf(key)) {
        windows++
        if (hourlySum(key, start, end) < total - tolerance24(total))
          short++
      }
    }
    expect(windows).toBe(112)
    // the hourly amounts alone leave these windows (days 5 to 10) short of the rain the totals have
    expect(short).toBe(56)
  })

  it('accounts for the 24 hour total in every one of those windows: the plan is never short of it by more than rounding', () => {
    for (const key of keys) {
      const plan = planPrecipitation(seriesOf(key))!
      for (const { start, end, total } of windowsOf(key)) {
        const over = precipitationOver(plan, start, end)
        expect(over.amount, `${key} +${(end - T(0)) / HOUR}`).toBeGreaterThanOrEqual(total - tolerance24(total) - 1e-9)
        // and no hour of the window is missing
        expect(over.given).toBe(24)
        expect(over.missing).toBe(0)
      }
    }
  })

  it('has the rain of days 6 to 10 where the hourly amount alone had none, at the station of the report (10382, the run of 03 UTC)', () => {
    const key = '10382@2026-11-17 03 UTC'
    const plan = planPrecipitation(seriesOf(key))!
    // the 24 hour windows that end at 06 UTC on the 22nd, 24th, 26th and 27th: DWD's totals 0.6, 0.8, 1.1 and 1.1 mm, the hourly amounts all 0.0
    const over = (end: number) => precipitationOver(plan, T(end) - 24 * HOUR, T(end))
    expect(over(150).amount).toBeCloseTo(0.6, 6)
    expect(over(198).amount).toBeCloseTo(0.8, 6)
    expect(over(222).amount).toBeCloseTo(1.2, 6)
    expect(over(246).amount).toBeCloseTo(1.2, 6)
    expect(over(150).longest).toBe(6)
    expect(over(222).longest).toBe(12)
    for (const end of [150, 198, 222, 246])
      expect(hourlySum(key, T(end) - 24 * HOUR, T(end)), `+${end}`).toBe(0)
  })

  it('goes from hourly amounts to 6 hour and then 12 hour blocks, and says where', () => {
    const plan = planPrecipitation(seriesOf('10382@2026-11-17 03 UTC'))!
    expect(plan.changes).toEqual([{ at: T(78), hours: 6 }, { at: T(174), hours: 12 }])
    expect(plan.longest).toBe(12)
    // each block is over the hours before its stamp, in order, none over another
    for (const block of plan.blocks)
      expect(block.start).toBe(block.end - block.hours * HOUR)
    // from the first hour the run gives (the one that ends at 04 UTC) to the last total, with no hour left out between
    expect(plan.blocks[0]!.start).toBe(T(3))
    expect(plan.blocks.at(-1)!.end).toBe(T(246))
    for (let i = 1; i < plan.blocks.length; i++)
      expect(plan.blocks[i]!.start, `block ${i}`).toBe(plan.blocks[i - 1]!.end)
  })

  it('does not rely on the 6 hour totals alone: where they too are 0.0 it takes the 12 hour totals, which carry the rain to the end (10147, the run of 03 UTC)', () => {
    // RR6c's last non-zero step is +117 h after the issue here, RRhc and RRdc have rain to +243 h
    const key = '10147@2026-11-17 03 UTC'
    const series = seriesOf(key)
    const six = series.get(PRECIPITATION.six)!
    const lastSix = six.x.filter((_, i) => six.y[i]! > 0).at(-1)!.getTime()
    expect((lastSix - Date.UTC(2026, 10, 17, 3)) / HOUR).toBeLessThanOrEqual(120)
    const plan = planPrecipitation(series)!
    const over = (end: number) => precipitationOver(plan, T(end) - 24 * HOUR, T(end))
    // the 24 hour windows to +174, +198, +222 and +246 h (DWD's totals 0.5, 0.5, 1.4 and 1.4 mm): 12 hour blocks, whose sums are the totals
    for (const [end, amount] of [[174, 0.5], [198, 0.5], [222, 1.4], [246, 1.4]] as const) {
      expect(over(end).longest, `+${end}`).toBe(12)
      expect(over(end).amount, `+${end}`).toBeCloseTo(amount, 6)
    }
  })

  it('keeps the hourly amounts all the way at the station where they carry the rain (Zugspitze, the run of 09 UTC)', () => {
    const plan = planPrecipitation(seriesOf('10961@2026-11-16 09 UTC'))!
    expect(plan.longest).toBe(1)
    expect(plan.changes).toEqual([])
    expect(plan.blocks).toHaveLength(247)
  })

  it('takes a window\'s 6 hour totals where one hourly day falls short, and stays with them: once coarser, a window never goes back to finer blocks (Zugspitze, the run of 15 UTC)', () => {
    const plan = planPrecipitation(seriesOf('10961@2026-11-16 15 UTC'))!
    expect(plan.changes.map(change => change.hours)).toEqual([6])
    // the cadence never gets finer from one block to the next, in any of the twelve runs
    for (const key of precipitationRunKeys()) {
      const hours = planPrecipitation(seriesOf(key))!.blocks.map(block => block.hours)
      expect(hours.every((h, i) => i === 0 || h >= hours[i - 1]!), key).toBe(true)
    }
  })

  it('keeps the cadence through the window with 0.3 mm that no series but the 24 hour total has (10147, the run of 03 UTC, +150 h)', () => {
    // DWD's total for the 24 hours to +150 h is 0.3 mm, the 6 and 12 hour totals are all 0.0: it is a trace, dry in every series, and the
    // window takes the 6 hour blocks the window before it had, with no 24 hour block for 0.3 mm
    const plan = planPrecipitation(seriesOf('10147@2026-11-17 03 UTC'))!
    const inWindow = plan.blocks.filter(block => block.end > T(126) && block.end <= T(150))
    expect(inWindow.map(block => block.hours)).toEqual([6, 6, 6, 6])
    expect(inWindow.every(block => block.amount === 0)).toBe(true)
  })

  it('does not take the whole run for hourly because one hourly amount is no 0 late in it (P0489, the run of 15 UTC: 0.4 mm at +222 h)', () => {
    // a rule that switches after the last hour with an amount would keep the hourly amounts to +222 h and show days 6 to 9 at 0 to 0.4 mm
    const key = 'P0489@2026-11-16 15 UTC'
    const plan = planPrecipitation(seriesOf(key))!
    for (const end of [150, 174, 198]) {
      const over = precipitationOver(plan, T(end) - 24 * HOUR, T(end))
      expect(over.amount, `+${end}`).toBeGreaterThan(1.3)
      expect(over.longest).toBeGreaterThanOrEqual(6)
    }
    expect(hourlySum(key, T(198) - 24 * HOUR, T(198))).toBe(0)
  })

  it('is no more for a dry run than for a wet one: the choice follows what the series agree on, not how much rain there is', () => {
    // every amount 0: a dry forecast stays hourly all the way, and no cadence is announced
    const dry = new Map<string, Series>([
      [PRECIPITATION.hour, steps(hourlyFrom(1, zeros(100)))],
      [PRECIPITATION.six, steps(Array.from({ length: 16 }, (_, i) => [6 * (i + 1), 0] as [number, number]))],
      [PRECIPITATION.twelve, steps(Array.from({ length: 8 }, (_, i) => [12 * (i + 1), 0] as [number, number]))],
      [PRECIPITATION.day, steps(Array.from({ length: 4 }, (_, i) => [24 * (i + 1), 0] as [number, number]))],
    ])
    const plan = planPrecipitation(dry)!
    expect(plan.longest).toBe(1)
    expect(plan.changes).toEqual([])
    expect(plan.blocks).toHaveLength(100)
    expect(plan.blocks.every(block => block.hours === 1 && block.amount === 0)).toBe(true)
    // and in a real run a window with no rain in DWD's total keeps the cadence of the one before it: 10382 at 03 UTC, the 24 hours to +174 h
    const real = planPrecipitation(seriesOf('10382@2026-11-17 03 UTC'))!
    expect(real.blocks.filter(block => block.end > T(150) && block.end <= T(174)).every(block => block.hours === 6)).toBe(true)
    expect(real.changes).toHaveLength(2)
  })
})

describe('the plan of a series made by hand', () => {
  /** 6 hour totals stamped at 6, 12, ... hours (the first at `first`) */
  const six = (amounts: number[], first = 6) => steps(amounts.map((amount, i) => [first + 6 * i, amount] as [number, number]))

  it('is none where the forecast has no precipitation', () => {
    expect(planPrecipitation(new Map())).toBeNull()
    expect(planPrecipitation(new Map([['temperature_air_2m', steps([[1, 3]])]]))).toBeNull()
  })

  it('is the hourly amounts where there is no coarser total to judge them by, which is MOSMIX-S: a missing hour is left out, not a 0 (GH-4175)', () => {
    const series = new Map([[PRECIPITATION.hour, steps([[1, 0.2], [2, 0.4], [4, 0.1], [5, 0]])]])
    const plan = planPrecipitation(series)!
    expect(plan.blocks.map(block => [block.end, block.amount])).toEqual([[T(1), 0.2], [T(2), 0.4], [T(4), 0.1], [T(5), 0]])
    expect(plan.changes).toEqual([])
    // the hour that ends at 03:00 is no part of the plan, and the rain over a span that holds it says so
    const over = precipitationOver(plan, T(0), T(5))
    expect(over.amount).toBeCloseTo(0.7, 6)
    expect(over.given).toBe(4)
    expect(over.missing).toBe(1)
    expect(precipitationTotal(plan).missing).toBe(1)
    expect(precipitationTotal(plan).amount).toBeCloseTo(0.7, 6)
  })

  it('takes the 6 hour totals where the hours before them sum to less than the 24 hour total by more than rounding, and the hourly ones where they do not', () => {
    // 48 hours from 00 UTC: the first day's hours add up to its total, the second day's are 0.0 where the total has 2.4 mm
    const hourly = steps(hourlyFrom(1, [...zeros(24).map((_, i) => i === 5 ? 1.2 : 0), ...zeros(24)]))
    const series = new Map([
      [PRECIPITATION.hour, hourly],
      [PRECIPITATION.six, six([1.2, 0, 0, 0, 0.6, 0.6, 0.6, 0.6])],
      [PRECIPITATION.day, steps([[24, 1.2], [48, 2.4]])],
    ])
    const plan = planPrecipitation(series)!
    expect(plan.blocks.filter(block => block.end <= T(24)).every(block => block.hours === 1)).toBe(true)
    expect(plan.blocks.filter(block => block.end > T(24)).map(block => [block.hours, block.amount])).toEqual([[6, 0.6], [6, 0.6], [6, 0.6], [6, 0.6]])
    expect(plan.changes).toEqual([{ at: T(24), hours: 6 }])
  })

  it('judges the agreement in millimetres, whatever unit the series are in', () => {
    // the second day in inches: a total of 1 mm, 6 hour totals of 0.25 mm and hourly amounts of 0. In inches the 1 mm is 0.04, which a
    // tolerance of 0.3 would take for 0 and the hourly amounts for the day's; in millimetres it is a millimetre the hourly amounts lack
    const inch = 25.4
    const series = new Map([
      [PRECIPITATION.hour, steps(hourlyFrom(1, zeros(48)))],
      [PRECIPITATION.six, six([0, 0, 0, 0, 0.25 / inch, 0.25 / inch, 0.25 / inch, 0.25 / inch])],
      [PRECIPITATION.day, steps([[24, 0], [48, 1 / inch]])],
    ])
    const plan = planPrecipitation(series, amount => amount * inch)!
    expect(plan.blocks.filter(block => block.end > T(24)).map(block => block.hours)).toEqual([6, 6, 6, 6])
  })

  it('does not use a series that gives a window only in part: an hour missing from it is no 0', () => {
    // the second day's hourly amounts have an hour missing (the one that ends at 06:00) and are 0.0 in the rest; the 6 hour totals have the rain
    const series = new Map([
      [PRECIPITATION.hour, steps(hourlyFrom(1, zeros(48)).filter(([hour]) => hour !== 30))],
      [PRECIPITATION.six, six([0, 0, 0, 0, 0.6, 0.6, 0.6, 0.6])],
      [PRECIPITATION.day, steps([[24, 0], [48, 2.4]])],
    ])
    const plan = planPrecipitation(series)!
    expect(plan.blocks.filter(block => block.end > T(24)).map(block => [block.hours, block.amount])).toEqual([[6, 0.6], [6, 0.6], [6, 0.6], [6, 0.6]])
  })

  it('ends a coarse stretch where its last total does: the hourly zeros after it are no dry hours', () => {
    // 30 hours of hourly 0.0 amounts under a 24 hour total of 2.4 mm that ends at 24: the 6 hours after it have no total
    const hourly = steps(hourlyFrom(1, zeros(30)))
    const dayOnly = planPrecipitation(new Map([[PRECIPITATION.hour, hourly], [PRECIPITATION.day, steps([[24, 2.4]])]]))!
    expect(dayOnly.blocks).toEqual([{ start: T(0), end: T(24), hours: 24, amount: 2.4 }])
    expect(dayOnly.changes).toEqual([])
    // 6 hour totals that go to 30 take the stretch on, in blocks of their own
    const withSix = planPrecipitation(new Map([[PRECIPITATION.hour, hourly], [PRECIPITATION.six, six([0.6, 0.6, 0.6, 0.6, 0])], [PRECIPITATION.day, steps([[24, 2.4]])]]))!
    expect(withSix.blocks.map(block => [block.hours, block.end - T(0)])).toEqual([[6, 6], [6, 12], [6, 18], [6, 24], [6, 30]].map(([hours, end]) => [hours, end! * HOUR]))
  })

  it('is the totals alone where there is no hourly amount at all, each over the hours it covers', () => {
    const series = new Map([[PRECIPITATION.six, six([0.4, 0])], [PRECIPITATION.twelve, steps([[12, 0.4], [24, 1.2]])]])
    const plan = planPrecipitation(series)!
    // the coarsest series gives the windows, the 12 hours to 12 and to 24: the 6 hour totals reach 12 and add up to the first, which is
    // then in blocks of 6 hours, and the second has none of them, so it is the 12 hour total itself
    expect(plan.blocks.map(block => [block.start, block.end, block.hours, block.amount])).toEqual([
      [T(0), T(6), 6, 0.4],
      [T(6), T(12), 6, 0],
      [T(12), T(24), 12, 1.2],
    ])
    expect(plan.changes).toEqual([{ at: T(12), hours: 12 }])
  })

  it('holds a window of 0.3 mm or less to be dry, which changes no cadence', () => {
    expect(TRACE_MM).toBe(0.3)
    const series = new Map([
      [PRECIPITATION.hour, steps(hourlyFrom(1, zeros(48)))],
      [PRECIPITATION.six, six(zeros(8))],
      [PRECIPITATION.day, steps([[24, 0.3], [48, 0.3]])],
    ])
    const plan = planPrecipitation(series)!
    expect(plan.longest).toBe(1)
    expect(plan.changes).toEqual([])
  })
})

describe('the rain over a local day', () => {
  const day = (iso: string) => {
    const start = DateTime.fromISO(iso, { zone: 'Europe/Berlin' }).startOf('day')
    return { from: start.toMillis(), to: start.plus({ days: 1 }).toMillis(), hours: (start.plus({ days: 1 }).toMillis() - start.toMillis()) / HOUR }
  }

  it('shares each 6 hour block out evenly over its hours, and cuts it where a local midnight crosses it', () => {
    // 2026-11-17 at Berlin is 23:00 UTC on the 16th to 23:00 on the 17th: the blocks that end at 00, 06, 12 and 18 UTC, and 5 of the 6 hours
    // of the one that ends at 24, which the midnight at 23:00 crosses
    const plan = planPrecipitation(new Map([[PRECIPITATION.six, steps([[0, 1], [6, 2], [12, 4], [18, 8], [24, 16]])]]))!
    const { from, to } = day('2026-11-17')
    const over = precipitationOver(plan, from, to)
    expect(from).toBe(Date.UTC(2026, 10, 16, 23))
    // the hour that ends at 00 UTC is the last of its block: a sixth of 1
    expect(over.amount).toBeCloseTo(1 / 6 + 2 + 4 + 8 + (5 / 6) * 16, 9)
    expect(over.longest).toBe(6)
    expect(over.given).toBe(24)
    expect(over.missing).toBe(0)
  })

  it('sums a day of 23 hours at the spring change of the clock, and one of 25 at the autumn change', () => {
    const spring = day('2026-03-29')
    const autumn = day('2026-10-25')
    expect([spring.hours, autumn.hours]).toEqual([23, 25])
    const from = Date.UTC(2026, 0, 1)
    const plan = planPrecipitation(new Map([[PRECIPITATION.six, { x: Array.from({ length: 4 * 365 }, (_, i) => new Date(from + 6 * (i + 1) * HOUR)), y: Array.from<number>({ length: 4 * 365 }).fill(1) }]]))!
    // 1 mm in 6 hours is 1/6 mm an hour, whatever the length of the day
    expect(precipitationOver(plan, spring.from, spring.to).amount).toBeCloseTo(23 / 6, 9)
    expect(precipitationOver(plan, autumn.from, autumn.to).amount).toBeCloseTo(25 / 6, 9)
    expect(precipitationOver(plan, spring.from, spring.to).given).toBe(23)
    expect(precipitationOver(plan, autumn.from, autumn.to).given).toBe(25)
  })

  it('adds the days up to the rain of the run, cut anywhere: every block is shared out whole', () => {
    const origin = Date.UTC(2026, 0, 1)
    const plan = planPrecipitation(new Map([[PRECIPITATION.six, { x: Array.from({ length: 16 }, (_, i) => new Date(origin + 6 * (i + 1) * HOUR)), y: Array.from<number>({ length: 16 }).fill(1) }]]))!
    // four days from the hour -5 to the hour 91: the plan begins at 0
    const sum = [0, 1, 2, 3].reduce((total, k) => total + precipitationOver(plan, origin + (k * 24 - 5) * HOUR, origin + ((k + 1) * 24 - 5) * HOUR).amount!, 0)
    expect(sum).toBeCloseTo(91 / 6, 9)
    expect(precipitationTotal(plan).amount).toBe(16)
  })

  it('is none for a span the plan has no hour of, and no hours are missing from it', () => {
    const plan = planPrecipitation(new Map([[PRECIPITATION.six, steps([[6, 1]])]]))!
    expect(precipitationOver(plan, T(48), T(72))).toEqual({ amount: null, given: 0, longest: 0, missing: 0, peak: null })
  })
})

describe('the rate of the wettest block of a span (GH-4193)', () => {
  it('is the rate of the wettest block over its hours, which a span cutting the block does not change', () => {
    // two blocks of 6 hours: 12 mm (2 an hour) and 30 mm (5 an hour); the span covers half of the first and a third of the second
    const plan = planPrecipitation(new Map([[PRECIPITATION.six, steps([[6, 12], [12, 30]])]]))!
    expect(precipitationOver(plan, T(3), T(8)).peak).toBe(5)
    expect(precipitationOver(plan, T(3), T(6)).peak).toBe(2)
  })
})

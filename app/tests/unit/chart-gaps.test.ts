import type { ExplorerSeries } from '../../app/utils/explorer-model'
import { describe, expect, it } from 'vitest'
import { boundsOf, buildTimeline, drawnPoints, gapRuleOf, pointCount, POINTS_PER_PX, readoutRows, valueAt } from '../../app/utils/explorer-model'

// Where rows are missing, a line is broken as it is where a value is (GH-4100): the rule that says where, and what is drawn of it

const HOUR = 3_600_000
const DAY = 24 * HOUR
const START = Date.UTC(2026, 8, 1)
const month = (year: number, index: number) => Date.UTC(year, index, 1)

function series(id: string, y: (number | null)[], over: Partial<ExplorerSeries> = {}, step = DAY): ExplorerSeries {
  return { id, name: id, colorIndex: 0, kind: 'values', x: y.map((_, i) => START + i * step), y, ...over }
}
const at = (...stamps: number[]) => ({ x: stamps, y: stamps.map(() => 1) })
const hours = (...offsets: number[]) => at(...offsets.map(offset => START + offset * HOUR))
/** The indices of the steps that the rule calls a gap: the step into the point at the index */
function gapsOf(data: { x: number[] }, resolution?: string) {
  const rule = gapRuleOf({ x: data.x, resolution })
  return rule ? data.x.flatMap((t, i) => i > 0 && rule(data.x[i - 1]!, t) ? [i] : []) : null
}

describe('the rule of a gap', () => {
  it('breaks an hourly series where a few hours are missing, and nowhere else', () => {
    expect(gapsOf(hours(0, 1, 2, 3, 4, 8, 9, 10, 11, 12), 'hourly')).toEqual([5])
  })

  it('counts one missing reading as a gap: a step of two hours in an hourly series', () => {
    expect(gapsOf(hours(0, 1, 2, 4, 5, 6), 'hourly')).toEqual([3])
  })

  it('goes by the resolution\'s interval, whatever the series\' own steps: 10 minutes, a day', () => {
    const tenMinutes = at(...[0, 1, 2, 3, 6, 7, 8].map(i => START + i * 600_000))
    expect(gapsOf(tenMinutes, '10_minutes')).toEqual([4])
    expect(gapsOf(series('d', [1, 2, 3, 4, 5, 6], {}, DAY), 'daily')).toEqual([])
    expect(gapsOf(at(START, START + DAY, START + 3 * DAY, START + 4 * DAY, START + 5 * DAY), 'daily')).toEqual([2])
  })

  it('does not take a change of clocks for a gap: the steps are UTC, and a day of 23 or 25 hours is a day', () => {
    // midnight in Berlin, in UTC, over the change to summer time (the 29th of March) and back (the 25th of October)
    const spring = at(Date.UTC(2026, 2, 27, 23), Date.UTC(2026, 2, 28, 23), Date.UTC(2026, 2, 29, 22), Date.UTC(2026, 2, 30, 22))
    expect(gapsOf(spring, 'daily')).toEqual([])
    const autumn = at(Date.UTC(2026, 9, 23, 22), Date.UTC(2026, 9, 24, 22), Date.UTC(2026, 9, 25, 23), Date.UTC(2026, 9, 26, 23))
    expect(gapsOf(autumn, 'daily')).toEqual([])
  })

  it('breaks a monthly series at a missing month, and not at the difference between a month of 28 and one of 31 days', () => {
    // March is missing: the step from February to April; January to February (31 days) and July to August (31) are none
    const months = at(month(2026, 0), month(2026, 1), month(2026, 3), month(2026, 4), month(2026, 5), month(2026, 6), month(2026, 7))
    expect(gapsOf(months, 'monthly')).toEqual([2])
    // February is missing: 59 days from the 1st of January to the 1st of March
    expect(gapsOf(at(month(2026, 0), month(2026, 2), month(2026, 3), month(2026, 4)), 'monthly')).toEqual([1])
    // a February of 28 days and one of 29 are months, and the step over the year's end is one
    expect(gapsOf(at(month(2025, 11), month(2026, 0), month(2026, 1), month(2026, 2)), 'monthly')).toEqual([])
    expect(gapsOf(at(month(2024, 0), month(2024, 1), month(2024, 2), month(2024, 3)), 'monthly')).toEqual([])
  })

  it('breaks an annual series at a missing year, and a leap year is no gap', () => {
    expect(gapsOf(at(month(2018, 0), month(2019, 0), month(2020, 0), month(2022, 0), month(2023, 0)), 'annual')).toEqual([3])
  })

  it('goes by the median step where the resolution names no interval', () => {
    const steps = hours(0, 3, 6, 9, 12, 24, 27, 30)
    expect(gapsOf(steps, 'subdaily')).toEqual([5])
    expect(gapsOf(steps)).toEqual([5])
  })

  it('holds a station that reports less often than its resolution to what it does: three-hourly readings of an hourly series are no gaps', () => {
    expect(gapsOf(hours(0, 3, 6, 9, 12, 15, 18, 30), 'hourly')).toEqual([7])
  })

  it('has no gaps in an irregular series: events are not shredded into dots', () => {
    // the steps of an event-driven series, in minutes: 4, 25, 180, 7, 70, 2880, 9, 41, 300, 16, 1200, 3
    let t = START
    const events = at(t, ...[4, 25, 180, 7, 70, 2880, 9, 41, 300, 16, 1200, 3].map(minutes => (t += minutes * 60_000)))
    expect(gapsOf(events, 'subdaily')).toBeNull()
    expect(gapsOf(events)).toBeNull()
    expect(gapsOf(events, '10_minutes')).toBeNull()
  })

  it('has no gap in a series of none, one or two points of no resolution: there is no usual step to compare with', () => {
    expect(gapsOf(at())).toBeNull()
    expect(gapsOf(at(START))).toBeNull()
    expect(gapsOf(at(START, START + 5 * DAY))).toEqual([])
    // two months of a monthly series five months apart: four are missing
    expect(gapsOf(at(month(2026, 0), month(2026, 5)), 'monthly')).toEqual([1])
  })

  it('has no gap in two points, whatever the resolution: their one step is the series\' own', () => {
    expect(gapsOf(at(START, START + 2 * DAY), 'hourly')).toEqual([])
  })

  it('has none for a trendline', () => {
    expect(gapRuleOf({ ...hours(0, 1, 100), kind: 'trend', resolution: 'hourly' })).toBeNull()
  })

  it('is the same rule for the same moments, not worked out again with each drag of the window', () => {
    const data = hours(0, 1, 2, 4)
    expect(gapRuleOf({ x: data.x, resolution: 'hourly' })).toBe(gapRuleOf({ x: data.x, resolution: 'hourly' }))
  })
})

describe('what is drawn of a gap', () => {
  // hourly for two days, 6 hours missing (the hours 48 to 53), 3 days, 3 days missing, a day
  const gappy = (): ExplorerSeries => {
    const offsets = [...Array.from({ length: 48 }, (_, i) => i), ...Array.from({ length: 72 }, (_, i) => 54 + i), ...Array.from({ length: 24 }, (_, i) => 198 + i)]
    return { ...series('g', offsets.map(() => 5), {}, HOUR), x: offsets.map(offset => START + offset * HOUR), resolution: 'hourly' }
  }
  const whole = (data: ExplorerSeries) => boundsOf([data])!
  const nulls = (drawn: { y: (number | null)[] }) => drawn.y.flatMap((value, i) => value === null ? [i] : [])

  it('is a point without a value between the two moments of a gap, in order, and none where the hours are all there', () => {
    const data = gappy()
    const drawn = drawnPoints(data, whole(data), 700, gapRuleOf(data))
    expect(nulls(drawn)).toEqual([48, 121])
    expect([...drawn.x].sort((a, b) => a - b)).toEqual(drawn.x)
    // in the middle of the 6 hours (the hour 47 to the hour 54), and every point of the data is there
    expect(drawn.x[48]).toBe(START + 50.5 * HOUR)
    expect(drawn.y.filter(value => value !== null)).toHaveLength(data.y.length)
  })

  it('leaves the series as it is: the table, the readout and the keys read what the data has', () => {
    const data = gappy()
    const before = JSON.stringify(data)
    drawnPoints(data, whole(data), 700, gapRuleOf(data))
    expect(JSON.stringify(data)).toBe(before)
    expect(pointCount(data)).toBe(144)
    expect(valueAt(data, START + 50 * HOUR)).toBeNull()
    expect(buildTimeline([data])).toHaveLength(144)
    expect(readoutRows([data], START + 50 * HOUR)).toEqual([])
  })

  it('is a gap of this series\' own: a series that has every hour is not broken where another has none', () => {
    const data = gappy()
    const full = { ...series('f', Array.from({ length: 222 }).fill(1), {}, HOUR), resolution: 'hourly' }
    expect(nulls(drawnPoints(full, whole(data), 700, gapRuleOf(full)))).toEqual([])
  })

  it('is as it was without a rule', () => {
    const data = gappy()
    expect(nulls(drawnPoints(data, whole(data), 700))).toEqual([])
  })

  it('is at the start of a window that begins inside a gap: no line from the point before the window to the first in it', () => {
    const data = gappy()
    const drawn = drawnPoints(data, { start: START + 52 * HOUR, end: START + 60 * HOUR }, 700, gapRuleOf(data))
    expect(drawn.y.slice(0, 3)).toEqual([5, null, 5])
    expect(drawn.x[0]).toBe(START + 47 * HOUR)
    expect(drawn.x[2]).toBe(START + 54 * HOUR)
  })

  it('is at the end of a window that ends inside a gap', () => {
    const data = gappy()
    const drawn = drawnPoints(data, { start: START + 40 * HOUR, end: START + 52 * HOUR }, 700, gapRuleOf(data))
    expect(drawn.x.at(-1)).toBe(START + 54 * HOUR)
    expect(drawn.y.slice(-3)).toEqual([5, null, 5])
  })

  it('is nothing across the gap where the window lies wholly inside it: the two points on either side, parted', () => {
    const data = gappy()
    expect(drawnPoints(data, { start: START + 49 * HOUR, end: START + 52 * HOUR }, 700, gapRuleOf(data)).y).toEqual([5, null, 5])
  })

  it('has no gap at the edge of a window that holds none', () => {
    const data = gappy()
    expect(nulls(drawnPoints(data, { start: START + 10 * HOUR, end: START + 30 * HOUR }, 700, gapRuleOf(data)))).toEqual([])
  })

  it('survives the cutting down of the points to the columns of a narrow plot', () => {
    const data = gappy()
    // 144 points on 20 px: more than 4 to a px, so the columns are made
    const drawn = drawnPoints(data, whole(data), 20, gapRuleOf(data))
    expect(drawn.x.length).toBeLessThan(data.x.length)
    // a column is 11 hours: the gap of 6 hours is narrower than it and is not to be seen, the gap of 72 hours is
    expect(nulls(drawn)).toHaveLength(1)
    // the points either side of it are the data's last before it and first after it
    const [at] = nulls(drawn)
    expect(drawn.x[at! - 1]).toBe(START + 125 * HOUR)
    expect(drawn.x[at! + 1]).toBe(START + 198 * HOUR)
  })

  it('keeps no break of a gap narrower than a column of the plot, whatever the points it parts', () => {
    const data = gappy()
    // 6 hours on a plot where a column is 11
    const drawn = drawnPoints(data, whole(data), 20, gapRuleOf(data))
    expect(drawn.x.some(t => t > START + 47 * HOUR && t < START + 54 * HOUR)).toBe(false)
  })

  it('is one break where a gap is also a run of missing values', () => {
    const data = { ...series('n', [1, 2, null, null, 5, 6], {}, HOUR), resolution: 'hourly' }
    expect(drawnPoints(data, whole(data), 700, gapRuleOf(data)).y).toEqual([1, 2, null, null, 5, 6])
    const sparse = { ...series('m', [1, 2, null, 5, 6], {}, HOUR), x: [0, 1, 2, 6, 7].map(i => START + i * HOUR), resolution: 'hourly' }
    expect(drawnPoints(sparse, whole(sparse), 700, gapRuleOf(sparse)).y).toEqual([1, 2, null, 5, 6])
  })

  const decade = (keep: (i: number) => boolean, resolution = 'hourly'): ExplorerSeries => {
    const stamps = Array.from({ length: 87_600 }, (_, i) => START + i * HOUR).filter((_, i) => keep(i))
    return { id: 'd', name: 'd', colorIndex: 0, kind: 'values', resolution, x: stamps, y: stamps.map((_, i) => Math.sin(i / 100)) }
  }
  const budget = 700 * POINTS_PER_PX
  const drawnOf = (data: ExplorerSeries) => drawnPoints(data, boundsOf([data])!, 700, gapRuleOf(data))

  it('is done for a decade of hourly readings in a few milliseconds, and keeps the gaps that are wide enough to see', () => {
    // 17 gaps of 500 hours, four columns of the plot each, and short ones of 5 hours
    const data = decade(i => i % 5000 > 499 && i % 1000 > 4)
    const win = boundsOf([data])!
    const began = performance.now()
    let drawn = drawnPoints(data, win, 700, gapRuleOf(data))
    for (let i = 0; i < 9; i++)
      drawn = drawnPoints(data, win, 700, gapRuleOf(data))
    expect((performance.now() - began) / 10).toBeLessThan(50)
    expect(nulls(drawn)).toHaveLength(17)
    expect(drawn.x.length).toBeLessThanOrEqual(budget + 100)
  })

  it('stays within the budget of points for a decade of readings with a gap every night (sunshine duration: rows from 03 to 20 UTC only)', () => {
    const data = decade(i => i % 24 >= 3 && i % 24 <= 20)
    const drawn = drawnOf(data)
    expect(drawn.x.length).toBeLessThanOrEqual(budget)
    expect(nulls(drawn)).toHaveLength(0)
  })

  it.each([0.05, 0.2])('stays within the budget of points where %s of the hours are missing at random, and draws no dots for gaps nobody sees', (share) => {
    let seed = 7
    const random = () => (seed = (seed * 16_807) % 2_147_483_647) / 2_147_483_647
    const data = decade(() => random() > share)
    const drawn = drawnOf(data)
    expect(drawn.x.length).toBeLessThanOrEqual(budget)
    expect(nulls(drawn)).toHaveLength(0)
  })
})

describe('the usual step of a series that reports at fixed times, or less often, or differently over time', () => {
  const stamps = (days: number, hoursOfDay: number[], without: (day: number, hour: number) => boolean = () => false) =>
    Array.from({ length: days }, (_, day) => hoursOfDay.map(hour => ({ day, hour }))).flat().filter(({ day, hour }) => !without(day, hour)).map(({ day, hour }) => START + day * DAY + hour * HOUR)

  it('has no gap in readings at 06, 12 and 18 UTC (steps of 6, 6 and 12 hours), and one where the 12:00 is missing', () => {
    expect(gapsOf(at(...stamps(300, [6, 12, 18])), 'subdaily')).toEqual([])
    const x = stamps(300, [6, 12, 18], (day, hour) => day === 100 && hour === 12)
    expect(gapsOf(at(...x), 'subdaily')).toEqual([x.indexOf(START + 100 * DAY + 18 * HOUR)])
  })

  it('has a gap for each of a missing 06:00, a missing 12:00 and a missing 18:00', () => {
    for (const missing of [6, 12, 18]) {
      const x = stamps(300, [6, 12, 18], (day, hour) => day === 100 && hour === missing)
      expect(gapsOf(at(...x), 'subdaily'), `${missing}:00 missing`).toHaveLength(1)
    }
  })

  it('has no gap in readings at 07 and 17 (steps of 10 and 14 hours), and one where a day is missing', () => {
    expect(gapsOf(at(...stamps(300, [7, 17])), 'subdaily')).toEqual([])
    expect(gapsOf(at(...stamps(300, [7, 17], day => day === 100)), 'subdaily')).toHaveLength(1)
  })

  it('has no gap in the same readings with no resolution named', () => {
    expect(gapsOf(at(...stamps(300, [6, 12, 18])))).toEqual([])
  })

  it('shows the gaps of an hourly series with half of its readings missing, as it does with few', () => {
    let seed = 3
    const random = () => (seed = (seed * 16_807) % 2_147_483_647) / 2_147_483_647
    const kept = Array.from({ length: 4000 }, (_, i) => START + i * HOUR).filter(() => random() > 0.5)
    const gaps = gapsOf(at(...kept), 'hourly')
    expect(gaps).not.toBeNull()
    // a step is a gap where it is 1.5 times the cadence round it, which is of one or two hours: so a lone missing hour is one, and a step of one is none
    expect(gaps!.length).toBeGreaterThan(0)
    expect(gaps!.every(i => kept[i]! - kept[i - 1]! > HOUR)).toBe(true)
    expect(gaps!.length).toBeLessThan(kept.length / 2)
  })

  it('shows the gaps of a monthly series with half of its months missing', () => {
    const months = Array.from({ length: 120 }, (_, i) => i).filter(i => i % 2 === 0 || i % 7 === 0).map(i => month(2010, i))
    expect(gapsOf(at(...months), 'monthly')!.length).toBeGreaterThan(10)
  })

  it('takes a change of cadence for none: a series that was 3-hourly and became hourly has no gap at the change, and has one in either era', () => {
    const x: number[] = []
    let t = START
    for (let i = 0; i < 400; i++, t += 3 * HOUR)
      x.push(t)
    const change = x.length
    for (let i = 0; i < 2000; i++, t += HOUR)
      x.push(t)
    expect(gapsOf(at(...x), 'hourly')).toEqual([])
    // a 3-hourly reading missing, and an hourly one
    const missed = x.filter((_, i) => i !== 200 && i !== change + 1000)
    expect(gapsOf(at(...missed), 'hourly')).toEqual([200, change + 999])
  })
})

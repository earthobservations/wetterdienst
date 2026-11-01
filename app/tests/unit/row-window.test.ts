import { describe, expect, it } from 'vitest'
import { limitRefusal } from '../../app/utils/limit-refusal'
import { aboutRows, countReadings, defaultRange, effectiveMaximum, estimateRows, fittingWindow, windowForRefusal } from '../../app/utils/row-window'

const NOW = Date.UTC(2026, 9, 26, 12)
const day = (text: string) => Date.parse(`${text}T00:00:00Z`)
function record(start: string | null, end: string | null = null) {
  return {
    start_timestamp: start ? `${start}T00:00:00+00:00` : null,
    // a record ends at its last reading, within its last day
    end_timestamp: end ? `${end}T23:59:59+00:00` : null,
  }
}
const spanOf = (start: string, end: string) => ({ start: day(start), end: day(end) })

describe('countReadings', () => {
  it.each([
    ['1_minute', '2026-01-01', '2026-01-01', 1440],
    ['5_minutes', '2026-01-01', '2026-01-01', 288],
    ['10_minutes', '2026-01-01', '2026-01-01', 144],
    ['hourly', '2026-01-01', '2026-01-01', 24],
    ['6_hours', '2026-01-01', '2026-01-01', 4],
    ['daily', '2026-01-01', '2026-01-31', 31],
    ['monthly', '2026-01-01', '2026-12-31', 12],
    ['annual', '2000-01-01', '2009-12-31', 10],
  ] as const)('counts a %s window from %s to %s (whole days) as %i readings', (resolution, from, to, expected) => {
    expect(countReadings(resolution, day(from), day(to) + 86_400_000 - 1)).toBe(expected)
  })

  it('counts a month or a year by its first day, which a window that begins after it does not hold', () => {
    expect(countReadings('monthly', day('2026-01-15'), day('2026-03-31'))).toBe(2)
    expect(countReadings('monthly', day('2026-01-15'), day('2026-01-31'))).toBe(0)
    expect(countReadings('annual', day('2000-06-01'), day('2002-12-31'))).toBe(2)
  })

  it('counts nothing for subdaily, which names no interval, and for a window that ends before it begins', () => {
    expect(countReadings('subdaily', day('2026-01-01'), day('2026-01-31'))).toBe(0)
    expect(countReadings('daily', day('2026-01-31'), day('2026-01-01'))).toBe(0)
  })
})

describe('estimateRows', () => {
  it('counts the readings of each station\'s record times the parameters', () => {
    const estimate = estimateRows({
      resolution: 'daily',
      records: [record('2020-01-01', '2020-01-31'), record('2020-01-01', '2020-01-10')],
      parameterCount: 3,
      now: NOW,
    })
    expect(estimate.rows).toBe((31 + 10) * 3)
    expect(estimate.span).toEqual(spanOf('2020-01-01', '2020-01-31'))
    expect(estimate.unknown).toBe(0)
  })

  it('counts 1-minute, 10-minute and hourly records', () => {
    const records = [record('2025-01-01', '2025-01-10')]
    expect(estimateRows({ resolution: '1_minute', records, parameterCount: 1, now: NOW }).rows).toBe(10 * 1440)
    expect(estimateRows({ resolution: '10_minutes', records, parameterCount: 2, now: NOW }).rows).toBe(10 * 144 * 2)
    expect(estimateRows({ resolution: 'hourly', records, parameterCount: 1, now: NOW }).rows).toBe(10 * 24)
  })

  it('counts a month and a year of monthly and annual records', () => {
    const records = [record('2000-01-01', '2009-12-31')]
    expect(estimateRows({ resolution: 'monthly', records, parameterCount: 2, now: NOW }).rows).toBe(120 * 2)
    expect(estimateRows({ resolution: 'annual', records, parameterCount: 1, now: NOW }).rows).toBe(10)
  })

  it('ends a record that has no end at now', () => {
    const estimate = estimateRows({ resolution: 'daily', records: [record('2026-10-01')], parameterCount: 1, now: NOW })
    // 1 to 26 October, the 26th at noon having begun
    expect(estimate.rows).toBe(26)
    expect(estimate.span).toEqual(spanOf('2026-10-01', '2026-10-26'))
  })

  it('counts a station once for each timestamp in the wide shape', () => {
    const records = [record('2020-01-01', '2020-01-10')]
    expect(estimateRows({ resolution: 'daily', records, parameterCount: 4, tidy: false, now: NOW }).rows).toBe(10)
  })

  it('narrows each record to the window the user gave, and the span with it', () => {
    const estimate = estimateRows({
      resolution: 'daily',
      records: [record('2000-01-01', '2020-12-31'), record('2015-01-01', '2016-12-31')],
      parameterCount: 1,
      range: { startDate: '2016-01-01', endDate: '2016-01-31' },
      now: NOW,
    })
    expect(estimate.rows).toBe(31 * 2)
    expect(estimate.span).toEqual(spanOf('2016-01-01', '2016-01-31'))
  })

  it('leaves a station out whose record ends before the window begins', () => {
    const estimate = estimateRows({
      resolution: 'daily',
      records: [record('2000-01-01', '2005-12-31'), record('2000-01-01', '2020-12-31')],
      parameterCount: 1,
      range: { startDate: '2016-01-01', endDate: '2016-01-31' },
      now: NOW,
    })
    expect(estimate.rows).toBe(31)
  })

  it('ignores a window with one date, as the request sends the end only after a start', () => {
    const records = [record('2020-01-01', '2020-01-10')]
    expect(estimateRows({ resolution: 'daily', records, parameterCount: 1, range: { startDate: '2020-01-05' }, now: NOW }).rows).toBe(10)
    expect(estimateRows({ resolution: 'daily', records, parameterCount: 1, range: { endDate: '2020-01-05' }, now: NOW }).rows).toBe(10)
  })

  it('takes a station without a start from the window, and counts it unknown without one', () => {
    const records = [record(null, null), record('2020-01-01', '2020-01-10')]
    const unbounded = estimateRows({ resolution: 'daily', records, parameterCount: 1, now: NOW })
    expect(unbounded.rows).toBe(10)
    expect(unbounded.unknown).toBe(1)
    const bounded = estimateRows({ resolution: 'daily', records, parameterCount: 1, range: { startDate: '2020-01-01', endDate: '2020-01-05' }, now: NOW })
    expect(bounded.rows).toBe(5 + 5)
    expect(bounded.unknown).toBe(0)
  })

  it('says nothing for a selection without a record to count, and for a resolution without an interval', () => {
    expect(estimateRows({ resolution: 'daily', records: [record(null)], parameterCount: 1, now: NOW })).toEqual({ rows: null, span: null, unknown: 1 })
    expect(estimateRows({ resolution: 'daily', records: [], parameterCount: 1, now: NOW }).rows).toBeNull()
    expect(estimateRows({ resolution: 'subdaily', records: [record('2020-01-01', '2020-01-31')], parameterCount: 1, now: NOW }).rows).toBeNull()
  })
})

describe('aboutRows', () => {
  it.each([[476_321, 480_000], [614_866, 610_000], [99_999, 100_000], [450, 450], [1234, 1200], [7, 7]])('says %i as about %i', (rows, about) => {
    expect(aboutRows(rows)).toBe(about)
  })
})

describe('fittingWindow', () => {
  // 1-minute data of one station and one parameter over three years: 1440 rows a day
  const threeYears = spanOf('2023-10-27', '2026-10-26')
  const threeYearsRows = 1096 * 1440

  it('takes the newest part that comes to 90 % of the limit, in days for a span that short', () => {
    // 90 % of 500,000 is 450,000: 312 days of 1440 readings are 449,280
    const window = fittingWindow({ requested: threeYearsRows, maximum: 500_000, resolution: '1_minute', span: threeYears })
    expect(window).toMatchObject({ unit: 'months', count: 10, endDate: '2026-10-26' })
    // 10 months, from 27 December 2025 to 26 October 2026: 304 days
    expect(window!.startDate).toBe('2025-12-27')
    expect(window!.rows).toBeLessThanOrEqual(450_000)
  })

  it('rounds down, never up: one day more than the window would not fit', () => {
    const window = fittingWindow({ requested: threeYearsRows, maximum: 500_000, resolution: '1_minute', span: threeYears })!
    const days = (Date.parse(`${window.endDate}T00:00:00Z`) - Date.parse(`${window.startDate}T00:00:00Z`)) / 86_400_000 + 1
    expect(days * 1440).toBeLessThanOrEqual(450_000)
    // the next month would not
    expect((days + 31) * 1440).toBeGreaterThan(450_000)
  })

  it('takes years of daily data, for the worked example of the issue', () => {
    // 614,866 daily rows of climate_summary for a few stations without a range: the window holds 450,000 of them
    const window = fittingWindow({ requested: 614_866, maximum: 500_000, resolution: 'daily', span: spanOf('1891-01-01', '2026-10-26') })
    // 135.8 years: 73.2 % of it, 99.4 years, rounded down to 99 years
    expect(window).toMatchObject({ unit: 'years', count: 99, endDate: '2026-10-26', startDate: '1927-10-27' })
    expect(window!.rows).toBeLessThanOrEqual(450_000)
  })

  it('answers null where the whole span fits', () => {
    expect(fittingWindow({ requested: 400_000, maximum: 500_000, resolution: 'daily', span: spanOf('2000-01-01', '2020-12-31') })).toBeNull()
    // between 90 % and 100 %: the margin is the reason to narrow, so there is a window
    expect(fittingWindow({ requested: 480_000, maximum: 500_000, resolution: 'daily', span: spanOf('2000-01-01', '2020-12-31') })).not.toBeNull()
  })

  it('answers null for no limit, no span and a limit too small to hold a reading', () => {
    expect(fittingWindow({ requested: 10, maximum: 0, resolution: 'daily', span: threeYears })).toBeNull()
    expect(fittingWindow({ requested: 600_000, maximum: 500_000, resolution: 'daily', span: null })).toBeNull()
    expect(fittingWindow({ requested: 10, maximum: 1, resolution: 'daily', span: threeYears })).toBeNull()
  })

  it('answers null where not even one day fits', () => {
    // a hundred stations of one parameter at 1-minute readings: 144,000 rows a day against a 100 rows limit
    expect(fittingWindow({ requested: 144_000 * 30, maximum: 100, resolution: '1_minute', span: spanOf('2026-09-27', '2026-10-26') })).toBeNull()
  })

  it('takes a tiny span apart in days', () => {
    // two days of which one fits: 100 rows a day against 150 allowed (90 % is 135)
    const window = fittingWindow({ requested: 200, maximum: 150, resolution: 'hourly', span: spanOf('2026-10-25', '2026-10-26') })
    expect(window).toMatchObject({ unit: 'days', count: 1, startDate: '2026-10-26', endDate: '2026-10-26' })
  })

  it('names months, not days, for monthly data, and years for annual data', () => {
    // 1,000 rows over 100 years of monthly data (1,200 months), 450 allowed: 37.5 %, 37 years
    const monthly = fittingWindow({ requested: 1000, maximum: 500, resolution: 'monthly', span: spanOf('1926-01-01', '2025-12-31') })
    expect(monthly!.unit).toBe('years')
    const shortMonthly = fittingWindow({ requested: 100, maximum: 50, resolution: 'monthly', span: spanOf('2025-01-01', '2025-03-31') })
    expect(shortMonthly!.unit).toBe('months')
    // a month does not fit and there is no smaller unit for it
    expect(fittingWindow({ requested: 1000, maximum: 20, resolution: 'monthly', span: spanOf('2025-01-01', '2025-12-31') })).toBeNull()
    const annual = fittingWindow({ requested: 1000, maximum: 500, resolution: 'annual', span: spanOf('1926-01-01', '2025-12-31') })
    expect(annual!.unit).toBe('years')
    // not a month of it
    expect(fittingWindow({ requested: 1000, maximum: 8, resolution: 'annual', span: spanOf('1926-01-01', '2025-12-31') })).toBeNull()
  })

  it('counts a month back from the end by the calendar, to the day before the same day of the month', () => {
    // 31 March less a month is 1 March, not 28 February
    const window = fittingWindow({ requested: 365, maximum: 40, resolution: 'daily', span: spanOf('2025-04-01', '2026-03-31') })
    expect(window).toMatchObject({ unit: 'months', count: 1, startDate: '2026-03-01', endDate: '2026-03-31' })
  })

  it('weights the days by what the stations hold, where the page knows it', () => {
    // all the rows of the span are in the first half: the newest half holds none, so the whole of it fits
    const span = spanOf('2020-01-01', '2020-12-31')
    const window = fittingWindow({
      requested: 1000,
      maximum: 500,
      resolution: 'daily',
      span,
      rowsWithin: (start, end) => (end < day('2020-07-01') ? 100 : start >= day('2020-07-01') ? 0 : 50),
    })
    expect(window).toMatchObject({ unit: 'months' })
    expect(window!.count).toBeGreaterThanOrEqual(6)
  })
})

describe('effectiveMaximum', () => {
  it('holds a high resolution to the page\'s own limit too', () => {
    expect(effectiveMaximum('1_minute', 500_000)).toBe(100_000)
    expect(effectiveMaximum('10_minutes', 0)).toBe(100_000)
    expect(effectiveMaximum('10_minutes', 50_000)).toBe(50_000)
    expect(effectiveMaximum('hourly', 500_000)).toBe(500_000)
    expect(effectiveMaximum('hourly', 0)).toBe(0)
  })
})

describe('windowForRefusal', () => {
  it('fits the server\'s own count: 1-minute data of one station over a given range', () => {
    // the whole 2025: 525,600 rows a parameter; the server refuses 1 parameter for 12 months at its 500,000 limit
    const window = windowForRefusal({
      resolution: '1_minute',
      records: [record('2020-01-01', '2026-10-25')],
      parameterCount: 1,
      range: { startDate: '2025-01-01', endDate: '2025-12-31' },
      requested: 525_600,
      maximum: 500_000,
      now: NOW,
    })
    // a high resolution is held to 100,000 rows: 90,000 rows are 62 days of 1440 readings
    expect(window).toMatchObject({ unit: 'months', count: 2, endDate: '2025-12-31', startDate: '2025-11-01' })
    expect(window!.rows).toBeLessThanOrEqual(90_000 + 1)
  })

  it('fits the daily example of the issue: all the record of several stations, no range', () => {
    const records = [record('1891-01-01', null), record('1936-01-01', null), record('1949-01-01', null), record('1901-01-01', null)]
    const whole = estimateRows({ resolution: 'daily', records, parameterCount: 4, now: NOW })
    const window = windowForRefusal({ resolution: 'daily', records, parameterCount: 4, requested: 614_866, maximum: 500_000, now: NOW })
    expect(whole.rows).toBeGreaterThan(450_000)
    expect(window!.unit).toBe('years')
    expect(window!.endDate).toBe('2026-10-26')
    // what the stations hold in the window, scaled to the server's total, is at most 90 % of the limit
    const inside = estimateRows({ resolution: 'daily', records, parameterCount: 4, range: { startDate: window!.startDate, endDate: window!.endDate }, now: NOW })
    expect(inside.rows! * 614_866 / whole.rows!).toBeLessThanOrEqual(450_000)
  })

  it('weighs the newest part by the stations that still deliver', () => {
    // one old station and one running: the newest years hold more of the rows than the span's average
    const records = [record('1950-01-01', '1980-12-31'), record('1950-01-01', null)]
    const window = windowForRefusal({ resolution: 'daily', records, parameterCount: 1, requested: 800_000, maximum: 500_000, now: NOW })
    const inside = estimateRows({ resolution: 'daily', records, parameterCount: 1, range: { startDate: window!.startDate, endDate: window!.endDate }, now: NOW })
    const whole = estimateRows({ resolution: 'daily', records, parameterCount: 1, now: NOW })
    expect(inside.rows! * 800_000 / whole.rows!).toBeLessThanOrEqual(450_000)
  })

  it('answers null for stations without a record and no range: there is no span to take a part of', () => {
    expect(windowForRefusal({ resolution: 'daily', records: [record(null)], parameterCount: 1, requested: 614_866, maximum: 500_000, now: NOW })).toBeNull()
  })

  it('fits a point, which is its range alone', () => {
    const window = windowForRefusal({
      resolution: 'hourly',
      records: [{}],
      parameterCount: 5,
      range: { startDate: '2000-01-01', endDate: '2025-12-31' },
      requested: 5 * 24 * 9497,
      maximum: 500_000,
      now: NOW,
    })
    expect(window).toMatchObject({ unit: 'years', endDate: '2025-12-31' })
  })
})

describe('defaultRange', () => {
  const base = { maxRows: 500_000, required: false, now: NOW }

  it('leaves the range empty where the whole record fits under 90 % of the limit', () => {
    expect(defaultRange({ ...base, resolution: 'daily', records: [record('1990-01-01', '2020-12-31')], parameterCount: 3 })).toEqual({ kind: 'none' })
  })

  it('starts a window where it does not', () => {
    const range = defaultRange({ ...base, resolution: 'daily', records: [record('1891-01-01', null), record('1936-01-01', null), record('1949-01-01', null), record('1900-01-01', null)], parameterCount: 5 })
    expect(range.kind).toBe('window')
    if (range.kind === 'window') {
      expect(range.window.rows).toBeLessThanOrEqual(450_000)
      expect(range.window.endDate).toBe('2026-10-26')
    }
  })

  it('takes the limit of the server and none at all as no range to start', () => {
    const records = [record('1891-01-01', null)]
    expect(defaultRange({ ...base, maxRows: 10_000, resolution: 'daily', records, parameterCount: 1 }).kind).toBe('window')
    expect(defaultRange({ ...base, maxRows: 0, resolution: 'daily', records, parameterCount: 1 })).toEqual({ kind: 'none' })
  })

  it('starts a high resolution at 90 % of the page\'s own 100,000, not the server\'s 500,000', () => {
    const range = defaultRange({ ...base, required: true, resolution: '10_minutes', records: [record('2000-01-01', null)], parameterCount: 1 })
    expect(range.kind).toBe('window')
    if (range.kind === 'window')
      expect(range.window.rows).toBeLessThanOrEqual(90_000)
  })

  it('fills a required range with the whole span where that fits, and leaves one that is not required empty', () => {
    const records = [record('2026-10-20', '2026-10-25')]
    expect(defaultRange({ ...base, required: true, resolution: 'hourly', records, parameterCount: 1 })).toEqual({ kind: 'whole', startDate: '2026-10-20', endDate: '2026-10-25' })
    expect(defaultRange({ ...base, resolution: 'hourly', records, parameterCount: 1 })).toEqual({ kind: 'none' })
  })

  it('says nothing for what the page cannot count: no record, subdaily, no start', () => {
    expect(defaultRange({ ...base, resolution: 'daily', records: [record(null)], parameterCount: 1 })).toEqual({ kind: 'none' })
    expect(defaultRange({ ...base, resolution: 'daily', records: [], parameterCount: 1 })).toEqual({ kind: 'none' })
    expect(defaultRange({ ...base, resolution: 'subdaily', records: [record('1990-01-01', null)], parameterCount: 1 })).toEqual({ kind: 'none' })
    // a range that is required is the span, counted or not
    expect(defaultRange({ ...base, required: true, resolution: 'subdaily', records: [record('1990-01-01', null)], parameterCount: 1 })).toMatchObject({ kind: 'whole', startDate: '1990-01-01' })
  })

  it('counts the stations that have a record and leaves one without out', () => {
    const range = defaultRange({ ...base, resolution: 'daily', records: [record(null), record('1891-01-01', null)], parameterCount: 10 })
    expect(range.kind).toBe('window')
  })
})

describe('limitRefusal', () => {
  const problem = { type: 'urn:wetterdienst:problem:limit-exceeded', status: 400, limit: 'rows', maximum: 500_000, requested: 614_866, detail: 'This request would return ...' }

  it('reads the fields of the problem, not its text', () => {
    expect(limitRefusal({ data: problem })).toEqual({ limit: 'rows', maximum: 500_000, requested: 614_866 })
    expect(limitRefusal({ data: JSON.stringify({ ...problem, limit: 'stations', maximum: 100, requested: 1284 }) })).toEqual({ limit: 'stations', maximum: 100, requested: 1284 })
  })

  it.each([
    ['another problem', { data: { ...problem, type: 'urn:wetterdienst:problem:server-busy' } }],
    ['a limit that is not known', { data: { ...problem, limit: 'bytes' } }],
    ['numbers that are text', { data: { ...problem, requested: '614866' } }],
    ['no numbers', { data: { ...problem, maximum: undefined } }],
    ['a body that is not JSON', { data: 'Bad Gateway' }],
    ['no body', {}],
    ['nothing', null],
  ])('is none for %s', (_name, error) => {
    expect(limitRefusal(error)).toBeNull()
  })
})

describe('a high resolution, counted as the date range form does', () => {
  // the form: every selected station over the window, every parameter whatever the shape, and no more than 100,000
  const formValues = (start: string, end: string, perDay: number, stations: number, parameters: number) =>
    ((day(end) - day(start)) / 86_400_000) * perDay * stations * parameters

  it('starts a window of the wide shape that the form accepts, as the form counts the parameters in it', () => {
    const range = defaultRange({
      resolution: '10_minutes',
      records: [record('1993-01-01', null)],
      parameterCount: 3,
      tidy: false,
      maxRows: 500_000,
      required: true,
      now: NOW,
    })
    expect(range.kind).toBe('window')
    if (range.kind !== 'window')
      return
    expect(formValues(range.window.startDate, range.window.endDate, 144, 1, 3)).toBeLessThanOrEqual(100_000)
  })

  it('counts a station whose record ended before the window too, as the form counts every station', () => {
    const range = defaultRange({
      resolution: '10_minutes',
      records: [record('1993-01-01', null), record('1993-01-01', '2000-12-31'), record('1993-01-01', '2000-12-31')],
      parameterCount: 1,
      maxRows: 500_000,
      required: true,
      now: NOW,
    })
    expect(range.kind).toBe('window')
    if (range.kind !== 'window')
      return
    expect(formValues(range.window.startDate, range.window.endDate, 144, 3, 1)).toBeLessThanOrEqual(100_000)
  })

  it('fits the refusal\'s window to the form too', () => {
    const window = windowForRefusal({
      resolution: '1_minute',
      records: [record('1993-01-01', null)],
      parameterCount: 2,
      tidy: false,
      requested: 3_000_000,
      maximum: 500_000,
      now: NOW,
    })!
    expect(formValues(window.startDate, window.endDate, 1440, 1, 2)).toBeLessThanOrEqual(100_000)
  })
})

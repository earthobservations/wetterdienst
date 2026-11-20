import type { DailyRow } from '../../server/utils/ghcnAnnual'
import { describe, expect, it } from 'vitest'
import { stripesFromRecord } from '../../app/utils/stripes-scale'
import {
  annualFromDaily,
  annualRows,
  leaveOutFailed,
  leaveOutSuspect,
  PRECIPITATION,
  TEMPERATURE_MAX,
  TEMPERATURE_MEAN,
  TEMPERATURE_MIN,
  temperatureMethod,
} from '../../server/utils/ghcnAnnual'
import * as stub from '../helpers/ghcn-stripes-stub'

// The annual values the stripes of NOAA's GHCN daily are made of, built from the days by the WMO rules (WMO-No. 1203) in the app's
// server (GH-4258). The cases are those of the backend's own tests of the module this is the port of
// (`tests/ui/test_stripes_annual.py`, GH-4222), and of the stub station of its tests of the stripes
// (`tests/ui/ghcn_stripes_stub.py`, `test_stripes_ghcn.py`): the same numbers, so that the port is held to the backend's answers.

type Day = string
const iso = (date: Date) => date.toISOString().slice(0, 10)
const days = (first: Day, last: Day): Day[] => stub.daysBetween(first, last)
const year = (y: number): Day[] => days(`${y}-01-01`, `${y}-12-31`)
/** Every day of the stub station's record */
const daysOfStub = () => days(`${stub.FIRST_YEAR}-01-01`, `${stub.LAST_YEAR}-12-31`)
const without = (all: Day[], ...gone: Day[]): Day[] => all.filter(day => !gone.includes(day))
const date = (y: number, m: number, d: number): Day => iso(new Date(Date.UTC(y, m - 1, d)))
const month = (y: number, m: number): Day[] => year(y).filter(day => Number(day.slice(5, 7)) === m)

/** The long frame of one parameter: a value for each of the days, a constant or by day */
function frame(parameter: string, on: Day[], value: number | Record<Day, number | null>): DailyRow[] {
  return on.map(day => ({ parameter, timestamp: `${day}T00:00:00.000000+00:00`, value: typeof value === 'number' ? value : (value[day] ?? null) }))
}

const temperature = (on: Day[], tmax = 10, tmin = 0): DailyRow[] => [...frame(TEMPERATURE_MAX, on, tmax), ...frame(TEMPERATURE_MIN, on, tmin)]

/** The answer as year to value */
const values = (rows: DailyRow[], kind: 'temperature' | 'precipitation' = 'temperature') => Object.fromEntries(annualFromDaily(rows, kind).map(item => [item.year, item.value]))

describe('the annual values of GHCN daily', () => {
  it('are one row a year at 1 January 00:00 UTC, as the answer of the server writes them', () => {
    const years = annualFromDaily(temperature(year(2000)), 'temperature')
    expect(years).toEqual([{ year: 2000, value: 5 }])
    expect(annualRows(years)).toEqual([{ timestamp: '2000-01-01T00:00:00.000000+00:00', value: 5 }])
  })

  it('are for a temperature the mean of the monthly means, not of the days: every month weighs the same', () => {
    const on = year(2000)
    // a mean of 10 in February alone (29 days in 2000), 0 in the other months
    const february = Object.fromEntries(on.map(day => [day, day.slice(5, 7) === '02' ? 20 : 0]))
    const rows = [...frame(TEMPERATURE_MAX, on, february), ...frame(TEMPERATURE_MIN, on, february)]
    const [value] = Object.values(values(rows))
    expect(value).toBeCloseTo(20 / 12, 3)
    // by the days it would be 20 * 29 / 366
    expect(Math.abs(value! - 20 * 29 / 366)).toBeGreaterThan(0.01)
  })

  it('make a day of the midrange, and a day with one of TMAX and TMIN is missing', () => {
    const on = year(2001)
    const march = month(2001, 3)
    const tmax = frame(TEMPERATURE_MAX, on, 30)
    // no TMIN on 3 days of March: TMAX alone is no mean, those days are missing (3 of 31, so the month still counts), and 11 would fail it
    const tmin = frame(TEMPERATURE_MIN, without(on, ...march.slice(0, 3)), 10)
    expect(values([...tmax, ...tmin])).toEqual({ 2001: 20 })
    const fewer = frame(TEMPERATURE_MIN, without(on, ...march.filter((_, index) => index % 2 === 0).slice(0, 11)), 10)
    expect(values([...tmax, ...fewer])).toEqual({ 2001: null })
  })

  it('are made of TAVG alone at a station with a TAVG and no TMAX or TMIN', () => {
    expect(values(frame(TEMPERATURE_MEAN, year(1999), 7.5))).toEqual({ 1999: 7.5 })
  })

  it('never use a TAVG beside a TMAX and TMIN, even on the days it has', () => {
    const on = year(1999)
    expect(values([...temperature(on, 30, 10), ...frame(TEMPERATURE_MEAN, on, 12)])).toEqual({ 1999: 20 })
  })

  it('show no step where a TAVG covers part of the record, 8 degrees under the midrange', () => {
    const on = [...year(2000), ...year(2001), ...year(2002)]
    const rows = [...temperature(on, 30, 10), ...frame(TEMPERATURE_MEAN, year(2001), 12)]
    expect(values(rows)).toEqual({ 2000: 20, 2001: 20, 2002: 20 })
  })

  it('name the method from the days read: the midrange where a day has both, a TAVG alone, nothing', () => {
    const on = year(2003)
    expect(temperatureMethod(temperature(on))).toBe('midrange')
    expect(temperatureMethod([...temperature(on), ...frame(TEMPERATURE_MEAN, on, 1)])).toBe('midrange')
    expect(temperatureMethod(frame(TEMPERATURE_MEAN, on, 1))).toBe('tavg')
    // TMAX and TMIN that never fall on the same day have no midrange: the TAVG is what is left
    const apart = [...frame(TEMPERATURE_MAX, on.slice(0, 100), 10), ...frame(TEMPERATURE_MIN, on.slice(100), 0)]
    expect(temperatureMethod(apart)).toBeNull()
    expect(temperatureMethod([...apart, ...frame(TEMPERATURE_MEAN, on, 5)])).toBe('tavg')
    expect(temperatureMethod(frame(PRECIPITATION, on, 1))).toBeNull()
    expect(temperatureMethod([])).toBeNull()
  })

  it.each([[10, true], [11, false]])('count a temperature month with at most 10 days missing: %i missing is valid: %s', (gone, valid) => {
    const on = year(2002)
    // every other day of March, so that no two missing days follow one another
    const march = month(2002, 3).filter((_, index) => index % 2 === 0).slice(0, gone)
    const value = values(temperature(without(on, ...march)))[2002]
    expect(value !== null).toBe(valid)
    if (valid)
      expect(value).toBe(5)
  })

  it.each([[4, true], [5, false]])('count a temperature month with at most 4 days missing in a row: %i in a row is valid: %s', (inARow, valid) => {
    const june = month(2003, 6)
    expect(values(temperature(without(year(2003), ...june.slice(9, 9 + inARow))))[2003] !== null).toBe(valid)
  })

  it('count runs in their month, so two short ones over the turn of a month count', () => {
    const gone = [date(2004, 1, 29), date(2004, 1, 30), date(2004, 1, 31), date(2004, 2, 1), date(2004, 2, 2)]
    expect(values(temperature(without(year(2004), ...gone)))[2004]).toBe(5)
  })

  it('count the missing days by the month, not the year: 10 in each of two months are fine', () => {
    const gone = [3, 4].flatMap(m => month(2005, m).filter((_, index) => index % 2 === 0).slice(0, 10))
    expect(values(temperature(without(year(2005), ...gone)))[2005]).toBe(5)
  })

  it('need all 12 months, and a year that fails is a gap between the others', () => {
    const on = [...year(2000), ...year(2001), ...year(2002)]
    // 2001 loses 11 days of a month
    expect(values(temperature(without(on, ...month(2001, 8).slice(0, 11))))).toEqual({ 2000: 5, 2001: null, 2002: 5 })
  })

  it('make a year the station has no row for a row of no value, so that the stripes show the hole', () => {
    expect(values(temperature([...year(1990), ...year(1993)]))).toEqual({ 1990: 5, 1991: null, 1992: null, 1993: 5 })
  })

  it('leave the years a record does not cover whole as gaps: it starts in July or has not reached December', () => {
    expect(values(temperature(days('1999-07-01', '2002-09-30')))).toEqual({ 1999: null, 2000: 5, 2001: 5, 2002: null })
  })

  it('end at the year of the last row, and start at the year of the first', () => {
    expect(Object.keys(values(temperature([...year(2010), ...year(2011)])))).toEqual(['2010', '2011'])
  })

  it.each([[10, true], [11, false]])('take null, NaN and an infinity for no day: %i of them are a valid month: %s', (count, valid) => {
    const on = year(2006)
    const bad = [null, Number.NaN, Infinity]
    const march = month(2006, 3).filter((_, index) => index % 2 === 0).slice(0, count)
    const tmax = on.map((day): DailyRow => ({ parameter: TEMPERATURE_MAX, timestamp: `${day}T00:00:00.000000+00:00`, value: march.includes(day) ? bad[march.indexOf(day) % 3]! : 10 }))
    expect(values([...tmax, ...frame(TEMPERATURE_MIN, on, 0)])[2006] !== null).toBe(valid)
  })

  it('count a precipitation month only when every day has a value', () => {
    const on = year(2007)
    expect(values(frame(PRECIPITATION, on, 2), 'precipitation')).toEqual({ 2007: expect.closeTo(2 * 365, 6) })
    expect(values(frame(PRECIPITATION, without(on, date(2007, 5, 17)), 2), 'precipitation')).toEqual({ 2007: null })
    // the same day on the temperature side is a valid month
    expect(values(temperature(without(on, date(2007, 5, 17))))).toEqual({ 2007: 5 })
  })

  it('make a precipitation year the sum of the monthly sums, a dry day being a value', () => {
    const on = year(2008)
    // 1 mm on the first day of each month, 0 on all others
    expect(values(frame(PRECIPITATION, on, Object.fromEntries(on.map(day => [day, day.endsWith('-01') ? 1 : 0]))), 'precipitation')).toEqual({ 2008: 12 })
  })

  it('take a precipitation value that is null for a missing day, as a day that is not in the file', () => {
    const on = year(2009)
    expect(values(frame(PRECIPITATION, on, { ...Object.fromEntries(on.map(day => [day, 1])), [date(2009, 2, 3)]: null }), 'precipitation')).toEqual({ 2009: null })
  })

  it('read the parameters of their kind only', () => {
    const on = year(2010)
    const rows = [...temperature(on), ...frame(PRECIPITATION, on, 1)]
    expect(values(rows)).toEqual({ 2010: 5 })
    expect(values(rows, 'precipitation')).toEqual({ 2010: 365 })
    expect(annualFromDaily(temperature(on), 'precipitation')).toEqual([])
    expect(annualFromDaily(frame(PRECIPITATION, on, 1), 'temperature')).toEqual([])
  })

  it('are none for no days', () => {
    expect(annualFromDaily([], 'temperature')).toEqual([])
    expect(annualFromDaily([], 'precipitation')).toEqual([])
    // rows with no value at all are no days either
    expect(annualFromDaily(frame(PRECIPITATION, year(2010), Object.fromEntries(year(2010).map(day => [day, null]))), 'precipitation')).toEqual([])
  })

  it('are rounded to three decimals: the mean of tenths comes out as no float\'s tail', () => {
    const on = year(2011)
    expect(values([...frame(TEMPERATURE_MAX, on, 10.1), ...frame(TEMPERATURE_MIN, on, 0.2)])[2011]).toBe(5.15)
  })
})

describe('a reading that failed a check', () => {
  const row = (flags: string | null | undefined): DailyRow => ({ parameter: TEMPERATURE_MAX, timestamp: '2000-01-01T00:00:00.000000+00:00', value: 3, quality_flags: flags })

  it.each([
    [null, true],
    [undefined, true],
    ['source:S', true],
    ['measurement:H,source:S', true],
    ['raw:-9999', true],
    ['G', false],
    ['G,source:S', false],
    ['measurement:H,I,source:S', false],
  ])('%j is kept: %s', (flags, kept) => {
    expect(leaveOutFailed([row(flags)])[0]!.value).toBe(kept ? 3 : null)
  })

  it('is the source\'s own plain code, and a suspect token is another check', () => {
    expect(leaveOutSuspect([row('G,source:S'), row('suspect:source'), row('I,source:Z,suspect:source')]).map(item => item.value)).toEqual([3, null, null])
  })

  it('leaves the rows of a frame without flags as they are', () => {
    const rows = [{ parameter: TEMPERATURE_MAX, timestamp: '2000-01-01T00:00:00.000000+00:00', value: 1 }]
    expect(leaveOutFailed(rows)).toEqual(rows)
  })
})

/** The stripes' years of the stub station, from its days as the server builds them, `{ year: value }` */
const stubYears = (rows: DailyRow[], kind: 'temperature' | 'precipitation') => values(leaveOutFailed(leaveOutSuspect(rows)), kind)

describe('the stub station of the backend\'s tests of the stripes', () => {
  it('has temperature years built from the days by the rules, a year a rule fails a gap, and a partial TAVG making no step', () => {
    const years = stubYears(stub.stubRows(), 'temperature')
    expect(Object.keys(years).map(Number)).toEqual(Array.from({ length: stub.LAST_YEAR - stub.FIRST_YEAR + 1 }, (_, index) => stub.FIRST_YEAR + index))
    // 11 days missing in a month, and 5 in a row: no year
    expect(years[2000]).toBeNull()
    expect(years[2005]).toBeNull()
    // 10 missing days, never more than 4 in a row, is a month that counts
    expect(years[2010]).toBeCloseTo(stub.meanTemperature(2010), 3)
    // the one year that has a TAVG, 1 degree under the midrange, is the midrange like the others: no step
    expect(years[stub.TAVG_YEAR]).toBeCloseTo(15, 3)
    expect(years[stub.TAVG_YEAR]).toBeCloseTo(stub.meanTemperature(stub.TAVG_YEAR), 3)
    for (const [y, value] of Object.entries(years)) {
      if (value !== null)
        expect(value).toBeCloseTo(stub.meanTemperature(Number(y)), 3)
    }
    expect(years[1990]).toBeCloseTo(10, 6)
    expect(years[1999]).toBeCloseTo(11.8, 3)
    expect(Object.entries(years).filter(([, value]) => value === null).map(([y]) => Number(y))).toEqual([2000, 2005])
  })

  it('has precipitation years that are the sums, a missing day making a gap, so 2010 fails as well', () => {
    const years = stubYears(stub.stubRows(), 'precipitation')
    expect(Object.entries(years).filter(([, value]) => value === null).map(([y]) => Number(y))).toEqual([2000, 2005, 2010])
    // 1 and 3 mm on alternate days: 2 mm a day, with the day a year has one more of in either direction
    expect(years[1991]).toBeCloseTo(stub.rainOf(1991), 6)
    expect(years[1992]).toBeCloseTo(stub.rainOf(1992), 6)
    expect(years[1991]).toBeGreaterThanOrEqual(728)
    expect(years[1991]).toBeLessThanOrEqual(732)
  })

  it('has, for the rest, the scale of the method on the years that have a value, and the whole record where it has too few', () => {
    const years = stubYears(stub.stubRows(), 'temperature')
    const record = Object.entries(years).map(([y, value]) => ({ year: Number(y), value }))
    const { values: items, reference } = stripesFromRecord(record, { stationId: stub.STATION })
    const present = record.filter(item => item.value !== null).map(item => item.value!)
    // 1990-2020 has 10 years with a value in 1971-2000 (of the 20 needed for the mean) and in 1901-2000 (of the 30 for the spread): both fall back to the whole record, the 29 years that have one
    expect(present).toHaveLength(29)
    for (const stat of [reference.centre, reference.spread]) {
      expect(stat.fallback).toBe(true)
      expect([stat.first_year, stat.last_year, stat.years]).toEqual([1990, 2020, 29])
    }
    expect(reference.centre.value).toBeCloseTo(present.reduce((sum, n) => sum + n, 0) / present.length, 9)
    const classes = items.map(item => item.stripe_class)
    // a gap has no class, and the warmest year has the highest
    expect(items.filter(item => item.value === null).map(item => item.stripe_class)).toEqual([null, null])
    expect(Math.max(...classes.filter((c): c is number => c !== null))).toBe(classes.at(-1))
    expect(items[0]!.anomaly).toBeCloseTo(10 - reference.centre.value, 3)
  })

  it('has years in the unit asked for, the conversion coming first, and the same classes in any unit', () => {
    const rows = stub.stubRows()
    const fahrenheit = rows.map(item => item.parameter.startsWith('temperature') ? { ...item, value: item.value! * 9 / 5 + 32 } : item)
    const celsiusYears = stubYears(rows, 'temperature')
    const fahrenheitYears = stubYears(fahrenheit, 'temperature')
    expect(fahrenheitYears[1990]).toBeCloseTo(50, 2)
    expect(fahrenheitYears[2000]).toBeNull()
    const classes = (record: Record<string, number | null>) => stripesFromRecord(Object.entries(record).map(([y, value]) => ({ year: Number(y), value })), { stationId: 'x' }).values.map(item => item.stripe_class)
    expect(classes(fahrenheitYears)).toEqual(classes(celsiusYears))
  })

  it('fails a month where 11 days of TMAX were flagged by NOAA\'s quality checks, as 11 missing days do, and the precipitation flagged on the same days', () => {
    const flagged = Array.from({ length: 11 }, (_, index) => date(1995, 3, 1 + 2 * index))
    const rows = stub.stubRows({ failed: flagged })
    const temperatureYears = stubYears(rows, 'temperature')
    expect(temperatureYears[1995]).toBeNull()
    expect(temperatureYears[1994]).not.toBeNull()
    expect(stubYears(rows, 'precipitation')[1995]).toBeNull()
  })

  it('has its years from TMAX and TMIN at a station with no TAVG', () => {
    expect(stubYears(stub.stubRows({ tavg: false }), 'temperature')[stub.TAVG_YEAR]).toBeCloseTo(15, 3)
  })

  it('has its years from the TAVG at a station that has no TMAX and TMIN, and names it', () => {
    const rows = stub.stubRows({ onlyTavg: true })
    const years = stubYears(rows, 'temperature')
    expect(temperatureMethod(leaveOutFailed(rows))).toBe('tavg')
    // the TAVG swings around the midrange of the stub, a tenth of a degree at most over a month
    expect(Math.abs(years[1990]! - 10)).toBeLessThanOrEqual(0.1)
    expect(Math.abs(years[1999]! - 11.8)).toBeLessThanOrEqual(0.1)
    expect(Object.entries(years).filter(([, value]) => value === null).map(([y]) => Number(y))).toEqual([2000, 2005])
  })

  it('names the midrange for a station with TMAX and TMIN, and no method for the precipitation', () => {
    const rows = leaveOutFailed(stub.stubRows())
    expect(temperatureMethod(rows)).toBe('midrange')
  })

  it('refuses a record of fewer valid years than the minimum, however many days they are made of', () => {
    const years = stubYears(stub.stubRows({ lastYear: 1998 }), 'temperature')
    expect(() => stripesFromRecord(Object.entries(years).map(([y, value]) => ({ year: Number(y), value })), { stationId: 'USW00000009' }))
      .toThrow(/At least 10 years with data are required to scale climate stripes/)
  })

  it('keeps the classes of the whole record where a window of years is shown', () => {
    const record = Object.entries(stubYears(stub.stubRows(), 'temperature')).map(([y, value]) => ({ year: Number(y), value }))
    const whole = stripesFromRecord(record, { stationId: 'x' })
    const window = stripesFromRecord(record, { stationId: 'x', startYear: 2011, endYear: 2014 })
    expect(window.values.map(item => item.timestamp?.slice(0, 4))).toEqual(['2011', '2012', '2013', '2014'])
    expect(window.reference).toEqual(whole.reference)
    expect(window.values.map(item => item.stripe_class)).toEqual(whole.values.filter(item => Number(item.timestamp?.slice(0, 4)) >= 2011 && Number(item.timestamp?.slice(0, 4)) <= 2014).map(item => item.stripe_class))
  })

  // the backend writes a row with no value for every day and element of a station that has none (`drop_nulls=false`), and the app asks
  // for none (`drop_nulls=true`, a third fewer rows): the rules read a missing row and a null alike, so the years do not change
  it.each([
    ['the stub station', stub.stubRows()],
    ['a station with a TAVG alone', stub.stubRows({ onlyTavg: true })],
    ['a station with failed checks', stub.stubRows({ failed: Array.from({ length: 11 }, (_, index) => date(1995, 3, 1 + 2 * index)) })],
  ])('has the same years from the rows that hold nulls as from the rows that do not: %s', (_name, rows) => {
    const parameters = ['precipitation_amount', 'temperature_air_mean_2m', 'temperature_air_max_2m', 'temperature_air_min_2m']
    const present = new Set(rows.map(row => `${row.timestamp}|${row.parameter}`))
    const nulls: DailyRow[] = daysOfStub().flatMap(day => parameters
      .filter(parameter => !present.has(`${day}T00:00:00.000000+00:00|${parameter}`))
      .map(parameter => ({ parameter, timestamp: `${day}T00:00:00.000000+00:00`, value: null, quality_flags: null })))
    expect(nulls.length).toBeGreaterThan(rows.length / 4)
    // as the rows come, the nulls among them
    const withNulls = [...rows, ...nulls].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    for (const kind of ['temperature', 'precipitation'] as const) {
      expect(stubYears(withNulls, kind)).toEqual(stubYears(rows, kind))
      expect(stubYears(withNulls, kind)).not.toEqual({})
    }
    expect(temperatureMethod(leaveOutFailed(withNulls))).toBe(temperatureMethod(leaveOutFailed(rows)))
  })
})

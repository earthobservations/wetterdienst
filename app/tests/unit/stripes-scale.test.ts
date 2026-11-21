import type { StripesReference } from '#shared/types/api'
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  CENTRE_PERIOD,
  CLASS_SIGMA,
  CLASSES,
  fsum,
  isSuspect,
  MIN_CENTRE_YEARS,
  MIN_RECORD_YEARS,
  MIN_SPREAD_YEARS,
  RANGE_SIGMA,
  roundHalfEven,
  SPREAD_PERIOD,
  stripeClass,
  stripesFromRecord,
  stripesReference,
  StripesRefusedError,
} from '../../app/utils/stripes-scale'

// The climate stripes' scale, which the app calculates itself (GH-4258). It is the port of the backend's `ui/stripes_scale.py`
// and of the years' part of `_get_stripes_data`, held here to the cases of the backend's own tests
// (`tests/ui/test_stripes_scale.py`): the golden file is a copy of the one that test writes, `tests/ui/stripes_scale.golden.json`.

interface Stat { value: number, first_year: number, last_year: number, years: number, fallback: boolean }
interface GoldenCase { name: string, years: number[], values: number[], reference: { centre: Stat, spread: Stat }, classes: number[] }
const GOLDEN: GoldenCase[] = JSON.parse(readFileSync(new URL('./stripes_scale.golden.json', import.meta.url), 'utf8'))

function reference(mean = 10, sigma = 1): StripesReference {
  const stat = { first_year: 1901, last_year: 2000, years: 100, fallback: false }
  return { centre: { value: mean, ...stat }, spread: { value: sigma, ...stat }, range_sigma: 2.6, classes: 16 }
}

/** A warming record: a value every year of `first` to `last` but the `gaps`, 8 degrees and 0.05 a year (the backend test's) */
function record(first: number, last: number, gaps: number[] = []) {
  const years = Array.from({ length: last - first + 1 }, (_, index) => first + index).filter(year => !gaps.includes(year))
  return { years, values: years.map(year => 8 + 0.05 * (year - 1900) + (year % 2 ? 0.3 : -0.3)) }
}

/** Python's `statistics.stdev` and `fmean`, for the reference to be held to */
const mean = (numbers: number[]) => numbers.reduce((sum, n) => sum + n, 0) / numbers.length
const stdev = (numbers: number[]) => Math.sqrt(numbers.reduce((sum, n) => sum + (n - mean(numbers)) ** 2, 0) / (numbers.length - 1))

describe('the cases of the backend', () => {
  it('are there to be held to: a case of each way a station is classed', () => {
    expect(GOLDEN.length).toBeGreaterThanOrEqual(4)
    // the method itself, a mean of the whole record, a spread of it, and an outlier
    expect(GOLDEN.map(item => [item.reference.centre.fallback, item.reference.spread.fallback])).toEqual(expect.arrayContaining([[false, false], [true, true], [false, true]]))
  })

  it.each(GOLDEN.map(item => [item.name, item] as const))('gives %s the reference and the classes of the backend', (_name, golden) => {
    const reference = stripesReference(golden.years, golden.values)
    for (const part of ['centre', 'spread'] as const) {
      const { value, ...rest } = golden.reference[part]
      expect(reference[part]).toMatchObject(rest)
      // the sum is the backend's own (`math.fsum`), so the numbers are the same to the last digits
      expect(reference[part].value).toBeCloseTo(value, 12)
    }
    expect(golden.values.map(value => stripeClass(value, reference))).toEqual(golden.classes)
    const { values } = stripesFromRecord(golden.years.map((year, index) => ({ year, value: golden.values[index]! })), { stationId: 'x' })
    expect(values.filter(item => item.value !== null).map(item => item.stripe_class)).toEqual(golden.classes)
  })
})

describe('the sum', () => {
  it('is exact where a plain sum is not, as Python\'s math.fsum', () => {
    expect(fsum(Array.from<number>({ length: 10 }).fill(0.1))).toBe(1)
    expect(Array.from<number>({ length: 10 }).fill(0.1).reduce((sum, n) => sum + n, 0)).not.toBe(1)
    expect(fsum([1e100, 1, -1e100])).toBe(1)
    expect(fsum([1e16, 1, 1])).toBe(1e16 + 2)
    expect(fsum([])).toBe(0)
    expect(fsum([-0.5])).toBe(-0.5)
  })
})

describe('the class of a value', () => {
  it('is 0.325 standard deviations wide, 2.6 / 8', () => {
    expect(CLASS_SIGMA).toBeCloseTo(0.325)
    expect([RANGE_SIGMA, CLASSES]).toEqual([2.6, 16])
  })

  it.each([
    [10.0, 8], // the centre is the boundary: the lowest class of the upper half
    [10.3, 8],
    [10.33, 9],
    [9.99, 7],
    [9.68, 7], // 0.32 below, within the first class below the centre
    [9.67, 6],
    [11.0, 11], // 1 sigma = 3.08 classes
    [9.0, 4],
    [12.58, 15], // the 8th class above: 2.58 sigma
    [12.6, 15], // 2.6 sigma, and what lies beyond takes the end class
    [13.0, 15],
    [100.0, 15],
    [7.43, 0], // -2.57 sigma: the 8th class below
    [7.4, 0],
    [7.0, 0],
    [-100.0, 0],
  ])('puts %f in class %i', (value, expected) => {
    expect(stripeClass(value, reference())).toBe(expected)
  })

  it('follows the spread of the record: the same anomaly is a class further out where it is narrower', () => {
    expect(stripeClass(11, reference(10, 1))).toBe(11)
    expect(stripeClass(11, reference(10, 0.25))).toBe(15)
    expect(stripeClass(11, reference(10, 2))).toBe(9)
  })

  it('takes the end a year lies at where the record has no spread, and the lowest class above the centre at the centre', () => {
    const flat = reference(10, 0)
    expect([10, 11, 9].map(value => stripeClass(value, flat))).toEqual([8, 15, 0])
  })
})

describe('the reference', () => {
  it('of a long record is the method\'s: the mean of 1971-2000 and the standard deviation of 1901-2000', () => {
    const { years, values } = record(1901, 2020)
    const reference = stripesReference(years, values)
    expect(reference.centre.value).toBeCloseTo(mean(values.filter((_, index) => years[index]! >= 1971 && years[index]! <= 2000)), 12)
    expect(reference.spread.value).toBeCloseTo(stdev(values.filter((_, index) => years[index]! <= 2000)), 12)
    expect([reference.centre.first_year, reference.centre.last_year, reference.centre.years]).toEqual([1971, 2000, 30])
    expect([reference.spread.first_year, reference.spread.last_year, reference.spread.years]).toEqual([1901, 2000, 100])
    expect([reference.centre.fallback, reference.spread.fallback]).toEqual([false, false])
    expect([reference.range_sigma, reference.classes]).toEqual([2.6, 16])
  })

  it('does not take the years after 2000: a warmer 2001 to 2020 does not move it, and is only classed', () => {
    const cut = record(1901, 2000)
    const full = record(1901, 2020)
    const reference = stripesReference(full.years, full.values)
    expect(reference).toEqual(stripesReference(cut.years, cut.values))
    expect(full.values.filter((_, index) => full.years[index]! > 2000).every(value => stripeClass(value, reference) >= 8)).toBe(true)
    expect(stripeClass(Math.max(...full.values), reference)).toBeGreaterThan(stripeClass(cut.values.at(-1)!, reference))
  })

  it.each([[MIN_CENTRE_YEARS, false], [MIN_CENTRE_YEARS - 1, true]])('takes the whole record for the mean of a station with %i years of 1971-2000: %s', (have, fallback) => {
    // a record of 1941 to 2020 whose 1971-2000 has `have` years: the others of those 30 are gaps
    const gaps = Array.from({ length: 30 - have }, (_, index) => 1971 + have + index)
    const { years, values } = record(1941, 2020, gaps)
    const reference = stripesReference(years, values)
    expect(reference.centre.fallback).toBe(fallback)
    if (fallback) {
      expect(reference.centre.value).toBeCloseTo(mean(values), 12)
      expect([reference.centre.first_year, reference.centre.last_year, reference.centre.years]).toEqual([1941, 2020, years.length])
    }
    else {
      expect(reference.centre.years).toBe(have)
      expect([reference.centre.first_year, reference.centre.last_year]).toEqual([1971, 1971 + have - 1])
    }
    // the spread has 60 years of 1901-2000 either way
    expect(reference.spread.fallback).toBe(false)
  })

  it.each([[MIN_SPREAD_YEARS, false], [MIN_SPREAD_YEARS - 1, true]])('takes the whole record for the spread of a station with %i years of 1901-2000: %s', (have, fallback) => {
    const { years, values } = record(2000 - have + 1, 2020)
    const reference = stripesReference(years, values)
    expect(reference.spread.fallback).toBe(fallback)
    expect(reference.spread.value).toBeCloseTo(stdev(fallback ? values : values.filter((_, index) => years[index]! <= 2000)), 12)
    // these have the 29 or 30 years of 1971-2000 the mean needs
    expect(reference.centre.fallback).toBe(false)
  })

  it('takes the whole record for both at a station that started in 1991', () => {
    const { years, values } = record(1991, 2020)
    const reference = stripesReference(years, values)
    expect([reference.centre.fallback, reference.spread.fallback]).toEqual([true, true])
    expect(reference.centre.value).toBeCloseTo(mean(values), 12)
    expect(reference.spread.value).toBeCloseTo(stdev(values), 12)
    expect([reference.centre.first_year, reference.centre.last_year, reference.centre.years]).toEqual([1991, 2020, 30])
  })

  it('spans the scale where the record is the reference: a year 2.6 sigma beyond the mean takes the end class', () => {
    const { years, values } = record(1991, 2020)
    const reference = stripesReference(years, values)
    const classes = values.map(value => stripeClass(value, reference))
    expect(classes.every(c => c >= 0 && c < 16)).toBe(true)
    expect(stripeClass(reference.centre.value + 2.6 * reference.spread.value + 1e-9, reference)).toBe(15)
    expect(stripeClass(reference.centre.value - 2.6 * reference.spread.value - 1e-9, reference)).toBe(0)
    // the warming shows: the first year is below the centre, the last above
    expect(classes[0]).toBeLessThan(8)
    expect(classes.at(-1)).toBeGreaterThanOrEqual(8)
  })

  it('has the thresholds and periods the docs state', () => {
    expect([MIN_CENTRE_YEARS, MIN_SPREAD_YEARS, MIN_RECORD_YEARS]).toEqual([20, 30, 10])
    expect([CENTRE_PERIOD, SPREAD_PERIOD]).toEqual([[1971, 2000], [1901, 2000]])
  })
})

describe('rounding', () => {
  // the numbers polars 2.0 gave (`pl.Series([...]).round(n)`, checked on 36,000 values, ties included): a tie goes to the even
  // neighbour, where a plain Math.round goes up and rounding away from zero goes out
  it('goes to the even neighbour at a tie, as the backend\'s polars does', () => {
    expect(roundHalfEven(-2.5, 0)).toBe(-2)
    expect(roundHalfEven(2.5, 0)).toBe(2)
    expect(roundHalfEven(1.5, 0)).toBe(2)
    expect(roundHalfEven(0.5, 0)).toBe(0)
    expect(roundHalfEven(0.00025, 4)).toBe(0.0002)
    expect(roundHalfEven(-0.00025, 4)).toBe(-0.0002)
    expect(roundHalfEven(0.0015, 3)).toBe(0.002)
    expect(roundHalfEven(0.0025, 3)).toBe(0.002)
    expect(roundHalfEven(-0.0025, 3)).toBe(-0.002)
    expect(Math.round(-2.5)).toBe(-2)
  })

  it('follows the scaled number where it is not exactly a tie, which the float has already decided', () => {
    expect(roundHalfEven(1.00005, 4)).toBe(1.0001)
    expect(roundHalfEven(-1.00005, 4)).toBe(-1.0001)
    expect(roundHalfEven(1.2345, 3)).toBe(1.234)
    expect(roundHalfEven(1.2355, 3)).toBe(1.236)
  })

  it('leaves a number that is no tie as it is, and a zero a zero', () => {
    expect(roundHalfEven(5.15, 3)).toBe(5.15)
    expect(roundHalfEven(-0.2, 4)).toBe(-0.2)
    expect(roundHalfEven(0, 3) + 0).toBe(0)
  })
})

describe('a reading flagged by a plausibility check', () => {
  it.each([
    [null, false],
    ['', false],
    ['1', false],
    ['9', false],
    ['source:S', false],
    ['raw:-9999', false],
    ['suspect:source', true],
    ['I,source:Z,suspect:source', true],
    ['source:0,suspect:relations', true],
    ['rejected:range,raw:99', false],
    ['not_suspect:1', false],
  ])('%j is suspect: %s', (flags, suspect) => {
    expect(isSuspect(flags)).toBe(suspect)
  })
})

describe('the stripes of a record', () => {
  const long = record(1901, 2020)
  const years = long.years.map((year, index) => ({ year, value: long.values[index]! }))

  it('are every year from the first to the last, the anomaly rounded to four places and the class of the whole record', () => {
    const { values, reference } = stripesFromRecord(years, { stationId: '01048' })
    expect(values).toHaveLength(120)
    expect(values[0]).toMatchObject({ timestamp: '1901-01-01T00:00:00.000000+00:00', value: years[0]!.value })
    expect(values[0]!.anomaly).toBe(Math.round((years[0]!.value - reference.centre.value) * 1e4) / 1e4)
    expect(values.map(item => item.stripe_class)).toEqual(years.map(item => stripeClass(item.value, reference)))
  })

  it('keep the reference and the classes of the whole record whatever window is shown', () => {
    const whole = stripesFromRecord(years, { stationId: 'x' })
    const window = stripesFromRecord(years, { stationId: 'x', startYear: 1990, endYear: 2000 })
    expect(window.reference).toEqual(whole.reference)
    expect(window.values.map(item => item.stripe_class)).toEqual(whole.values.slice(1990 - 1901, 2001 - 1901).map(item => item.stripe_class))
    expect(window.values.map(item => item.timestamp?.slice(0, 4))).toEqual(Array.from({ length: 11 }, (_, index) => String(1990 + index)))
  })

  it('draw a year with no value as a row with none, between the years that have one', () => {
    const gappy = years.map(item => item.year === 2000 ? { ...item, value: null } : item)
    const { values } = stripesFromRecord(gappy, { stationId: 'x' })
    const gap = values.find(item => item.timestamp?.startsWith('2000'))!
    expect([gap.value, gap.anomaly, gap.stripe_class]).toEqual([null, null, null])
    expect(values).toHaveLength(120)
  })

  it('fill a year the record has no row for, as the backend upsamples to every year', () => {
    const { values } = stripesFromRecord(years.filter(item => item.year !== 1950 && item.year !== 1951), { stationId: 'x' })
    expect(values).toHaveLength(120)
    expect(values.filter(item => item.value === null).map(item => item.timestamp?.slice(0, 4))).toEqual(['1950', '1951'])
  })

  it('run from the first year with a value to the last inside the window: a window that starts in a gap does not label a year none shows', () => {
    const gappy = years.filter(item => item.year < 1990 || item.year > 1995)
    const { values } = stripesFromRecord(gappy, { stationId: 'x', startYear: 1992, endYear: 2000 })
    expect(values[0]!.timestamp).toBe('1996-01-01T00:00:00.000000+00:00')
    expect(values.at(-1)!.timestamp).toBe('2000-01-01T00:00:00.000000+00:00')
  })

  it('leave out a value that is no number and a record in any order', () => {
    const shuffled = [...years].reverse().map(item => item.year === 2010 ? { ...item, value: Number.NaN } : item.year === 2011 ? { ...item, value: Infinity } : item)
    const { values, reference } = stripesFromRecord(shuffled, { stationId: 'x' })
    expect(values.map(item => item.timestamp?.slice(0, 4))[0]).toBe('1901')
    expect(values.filter(item => item.value === null).map(item => item.timestamp?.slice(0, 4))).toEqual(['2010', '2011'])
    expect(Number.isFinite(reference.centre.value)).toBe(true)
  })

  it('refuse a window with fewer than two years with data, naming the record', () => {
    expect(() => stripesFromRecord(years, { stationId: '01048', startYear: 2030, endYear: 2040 }))
      .toThrow('At least two years with data are required to create climate stripes; station 01048 has data from 1901 to 2020')
    expect(() => stripesFromRecord([], { stationId: '01048' }))
      .toThrow('station 01048 has data for no year')
    expect(() => stripesFromRecord(years.map(item => ({ ...item, value: null })), { stationId: '01048' }))
      .toThrow('station 01048 has data for no year')
  })

  it('refuse a record of fewer years than a scale needs, as a 400 that names its years', () => {
    const short = record(1991, 1999)
    const refusal = (() => {
      try {
        stripesFromRecord(short.years.map((year, index) => ({ year, value: short.values[index]! })), { stationId: '00061' })
      }
      catch (error) {
        return error as StripesRefusedError
      }
    })()
    expect(refusal).toBeInstanceOf(StripesRefusedError)
    expect(refusal!.statusCode).toBe(400)
    expect(refusal!.data).toMatchObject({ status: 400, detail: 'At least 10 years with data are required to scale climate stripes; station 00061 has data for 9 (from 1991 to 1999)' })
    // ten years are enough
    const ten = record(1991, 2000)
    expect(() => stripesFromRecord(ten.years.map((year, index) => ({ year, value: ten.values[index]! })), { stationId: 'x' })).not.toThrow()
  })

  it('refuse a window whose end does not follow its start as the API\'s 422, naming end_year', () => {
    const refusal = (() => {
      try {
        stripesFromRecord(years, { stationId: 'x', startYear: 1990, endYear: 1990 })
      }
      catch (error) {
        return error as StripesRefusedError
      }
    })()
    expect(refusal!.statusCode).toBe(422)
    expect(refusal!.data.detail).toBe('end_year: Input should be greater than start_year (1990)')
    expect(refusal!.data.errors).toEqual([{ loc: ['query', 'end_year'], msg: 'Input should be greater than start_year (1990)' }])
  })
})

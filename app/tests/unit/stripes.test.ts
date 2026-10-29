import { describe, expect, it } from 'vitest'
import { compareWithNormal, stripeClass, stripeYears } from '../../app/utils/stripes'
import { unitSymbol } from '../../app/utils/unit-targets'

describe('stripe classes', () => {
  it.each([
    [0, 'veryLow'],
    [1.99, 'veryLow'],
    [2, 'low'],
    [3.99, 'low'],
    [4, 'middle'],
    [5.99, 'middle'],
    [6, 'high'],
    [7.99, 'high'],
    [8, 'veryHigh'],
    [10, 'veryHigh'],
  ] as const)('puts %s, in a range of 0 to 10, in the fifth %s', (value, expected) => {
    expect(stripeClass(value, 0, 10)).toBe(expected)
  })

  it('puts years that are all alike in the middle, where the colour scale has no range to put them on', () => {
    expect(stripeClass(7, 7, 7)).toBe('middle')
  })
})

describe('years of the stripes', () => {
  it('lists the years that are drawn, each with its value and class, and none without a value', () => {
    expect(stripeYears([
      { timestamp: '2018-01-01T00:00:00+00:00', value: 8 },
      { timestamp: '2019-01-01T00:00:00+00:00', value: null },
      { timestamp: null, value: 9 },
      { timestamp: '2021-01-01T00:00:00+00:00', value: 10 },
    ])).toEqual([
      { year: 2018, value: 8, class: 'veryLow' },
      { year: 2021, value: 10, class: 'veryHigh' },
    ])
  })

  it('reads each year in UTC, as the stripes do', () => {
    // the first moment of 2020 in UTC is still 2019 west of it
    const [first] = stripeYears([{ timestamp: '2020-01-01T00:00:00+00:00', value: 1 }])
    expect(first!.year).toBe(2020)
  })
})

describe('the takeaway of the stripes: the latest ten years against 1961-1990', () => {
  const series = (from: number, to: number, value: (year: number) => number) =>
    Array.from({ length: to - from + 1 }, (_, index) => ({ year: from + index, value: value(from + index) }))

  it('compares the mean of the last ten years drawn with the mean of the normal', () => {
    const years = series(1950, 2025, year => (year >= 2016 ? 10 : 8))
    expect(compareWithNormal(years)).toEqual({
      recentFrom: 2016,
      recentTo: 2025,
      recentMean: 10,
      normalFrom: 1961,
      normalTo: 1990,
      normalMean: 8,
      difference: 2,
      ratio: 0.25,
    })
  })

  it('says how much colder, too', () => {
    expect(compareWithNormal(series(1950, 2025, year => (year >= 2016 ? 7 : 8)))?.difference).toBe(-1)
  })

  it('tells nothing where the normal is not drawn well enough: fewer than 27 of its 30 years', () => {
    const gappy = series(1950, 2025, () => 8).filter(year => year.year < 1961 || year.year > 1964)
    expect(compareWithNormal(gappy)).toBeNull()
    const enough = series(1950, 2025, () => 8).filter(year => year.year < 1961 || year.year > 1963)
    expect(compareWithNormal(enough)).not.toBeNull()
  })

  it('tells nothing where fewer than 8 of the latest ten years are drawn', () => {
    const years = series(1950, 2025, () => 8).filter(year => year.year < 2017 || year.year > 2019)
    expect(compareWithNormal(years)).toBeNull()
  })

  it('tells nothing where the latest years reach into the normal itself, or there are none', () => {
    expect(compareWithNormal(series(1955, 1999, () => 8))).toBeNull()
    expect(compareWithNormal([])).toBeNull()
  })

  it('gives no ratio for a normal whose mean is not above zero (a temperature below freezing)', () => {
    expect(compareWithNormal(series(1950, 2025, year => (year >= 2016 ? 1 : -2)))?.ratio).toBeNull()
  })
})

describe('unit symbols', () => {
  it('writes the units the stripes come in as a number is written with them', () => {
    expect(unitSymbol('degree_celsius')).toBe('°C')
    expect(unitSymbol('millimeter')).toBe('mm')
  })

  it('names any other unit by its words', () => {
    expect(unitSymbol('meter_per_second')).toBe('meter per second')
  })
})

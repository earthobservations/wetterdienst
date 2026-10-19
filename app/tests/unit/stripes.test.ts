import { describe, expect, it } from 'vitest'
import { stripeClass, stripeYears } from '../../app/utils/stripes'
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

describe('unit symbols', () => {
  it('writes the units the stripes come in as a number is written with them', () => {
    expect(unitSymbol('degree_celsius')).toBe('°C')
    expect(unitSymbol('millimeter')).toBe('mm')
  })

  it('names any other unit by its words', () => {
    expect(unitSymbol('meter_per_second')).toBe('meter per second')
  })
})

import { describe, expect, it } from 'vitest'
import { COLOR_MAPS, stripeClass, stripeColour, stripesSummaryParams, stripeYears, wrapChartTitle } from '../../app/utils/stripes'
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

describe('the colour of a stripe', () => {
  it('is the colour of the scale\'s stop where the position is one, as Plotly draws it', () => {
    expect(stripeColour(COLOR_MAPS.temperature, 0)).toBe('rgb(5, 48, 97)')
    expect(stripeColour(COLOR_MAPS.temperature, 0.5)).toBe('rgb(247, 247, 247)')
    expect(stripeColour(COLOR_MAPS.temperature, 1)).toBe('rgb(178, 24, 43)')
  })

  it('is mixed between the two stops around the position', () => {
    // half way between the stops 0.4 (146,197,222) and 0.5 (247,247,247)
    expect(stripeColour(COLOR_MAPS.temperature, 0.45)).toBe('rgb(197, 222, 235)')
  })

  it('is the end of the scale for a position beyond it', () => {
    expect(stripeColour(COLOR_MAPS.temperature, -3)).toBe('rgb(5, 48, 97)')
    expect(stripeColour(COLOR_MAPS.temperature, 7)).toBe('rgb(178, 24, 43)')
  })

  it('is blue for the coldest and red for the warmest year of the temperature, brown to green for the precipitation', () => {
    const channelsOf = (css: string) => css.match(/\d+/g)!.map(Number) as [number, number, number]
    const [coldR, , coldB] = channelsOf(stripeColour(COLOR_MAPS.temperature, 0))
    const [warmR, , warmB] = channelsOf(stripeColour(COLOR_MAPS.temperature, 1))
    expect(coldB).toBeGreaterThan(coldR)
    expect(warmR).toBeGreaterThan(warmB)
    expect(stripeColour(COLOR_MAPS.precipitation, 0)).not.toBe(stripeColour(COLOR_MAPS.precipitation, 1))
  })
})

describe('the sentence that says what stripes show', () => {
  it('names the years it spans and the lowest and the highest year with its value', () => {
    const years = stripeYears([
      { timestamp: '2018-01-01T00:00:00+00:00', value: 8 },
      { timestamp: '2019-01-01T00:00:00+00:00', value: 12 },
      { timestamp: '2020-01-01T00:00:00+00:00', value: 9 },
    ])
    expect(stripesSummaryParams(years, value => `${value} °C`)).toEqual({ from: 2018, to: 2020, min: '8 °C', minYear: 2018, max: '12 °C', maxYear: 2019 })
  })
})

describe('wrapChartTitle', () => {
  const title = 'Climate stripes (Temperature) for Donaueschingen (Landeplatz), Germany (00011)'

  it('leaves a title that fits the width in one line', () => {
    expect(wrapChartTitle(title, 645, 16)).toEqual({ text: title, lines: 1 })
  })

  it('breaks a title at spaces into lines that fit the width', () => {
    const { text, lines } = wrapChartTitle(title, 236, 16)
    expect(lines).toBe(3)
    expect(text.split('<br>')).toEqual(['Climate stripes (Temperature)', 'for Donaueschingen', '(Landeplatz), Germany (00011)'])
    expect(text.split('<br>').every(line => line.length <= Math.floor(236 / 8))).toBe(true)
    // nothing is lost or added but the breaks
    expect(text.replaceAll('<br>', ' ')).toBe(title)
  })

  it('keeps a word wider than the width whole on a line of its own', () => {
    expect(wrapChartTitle('a Donaueschingen b', 40, 16)).toEqual({ text: 'a<br>Donaueschingen<br>b', lines: 3 })
  })
})

import { describe, expect, it } from 'vitest'
import { STRIPE_CLASS_COUNT, STRIPE_CLASSES, STRIPE_PALETTES, stripeBand, stripeColour, stripesReferenceText, stripesSummaryParams, stripeYears, wrapChartTitle } from '../../app/utils/stripes'
import { unitSymbol } from '../../app/utils/unit-targets'

const answer = (...items: [string | null, number | null, number | null, number | null][]) => items.map(([timestamp, value, anomaly, stripe_class]) => ({ timestamp, value, anomaly, stripe_class }))

describe('the bands a class is told in', () => {
  it.each([
    [0, 'veryLow'],
    [2, 'veryLow'],
    [3, 'low'],
    [6, 'low'],
    [7, 'middle'],
    [8, 'middle'],
    [9, 'high'],
    [12, 'high'],
    [13, 'veryHigh'],
    [15, 'veryHigh'],
  ] as const)('puts the class %s in the band %s', (stripeClass, expected) => {
    expect(stripeBand(stripeClass)).toBe(expected)
  })

  it('names each of the 16 classes in one of five bands that are symmetric round the centre', () => {
    const bands = Array.from({ length: STRIPE_CLASS_COUNT }, (_, stripeClass) => stripeBand(stripeClass))
    expect(new Set(bands)).toEqual(new Set(STRIPE_CLASSES))
    const mirror = (band: string) => ({ veryLow: 'veryHigh', low: 'high', middle: 'middle', high: 'low', veryHigh: 'veryLow' })[band]
    expect(bands.map(mirror)).toEqual([...bands].reverse())
  })
})

describe('years of the stripes', () => {
  it('lists the years that are drawn, each with its value, anomaly and the class the backend gave it, and none without a value', () => {
    expect(stripeYears(answer(
      ['2018-01-01T00:00:00+00:00', 8, -1.5, 2],
      ['2019-01-01T00:00:00+00:00', null, null, null],
      [null, 9, 0, 8],
      ['2021-01-01T00:00:00+00:00', 10, 2.5, 15],
    ))).toEqual([
      { year: 2018, value: 8, anomaly: -1.5, stripeClass: 2, class: 'veryLow' },
      { year: 2021, value: 10, anomaly: 2.5, stripeClass: 15, class: 'veryHigh' },
    ])
  })

  it('reads each year in UTC, as the stripes do', () => {
    // the first moment of 2020 in UTC is still 2019 west of it
    const [first] = stripeYears(answer(['2020-01-01T00:00:00+00:00', 1, 0, 8]))
    expect(first!.year).toBe(2020)
  })

  it('does not class the years itself: a class is the one of the answer, whatever the years around it are', () => {
    // the same value in a record of two years and in one of many keeps the class it was given
    expect(stripeYears(answer(['2000-01-01T00:00:00+00:00', 5, 1, 11], ['2001-01-01T00:00:00+00:00', 5, 1, 11])).map(year => year.stripeClass)).toEqual([11, 11])
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
  it('is the last of the palette for the highest class and the first for the lowest', () => {
    expect(stripeColour('temperature', 0)).toBe('#08306b')
    expect(stripeColour('temperature', 15)).toBe('#67000d')
    expect(stripeColour('precipitation', 0)).toBe('#543005')
    expect(stripeColour('precipitation', 15)).toBe('#003c30')
  })

  it('has 16 different colours for each kind, blue below the centre and red above it for the temperature', () => {
    const channelsOf = (hex: string) => [1, 3, 5].map(at => Number.parseInt(hex.slice(at, at + 2), 16)) as [number, number, number]
    for (const kind of ['temperature', 'precipitation'] as const) {
      expect(STRIPE_PALETTES[kind]).toHaveLength(16)
      expect(new Set(STRIPE_PALETTES[kind]).size).toBe(16)
    }
    for (let stripeClass = 0; stripeClass < 8; stripeClass++) {
      const [r, , b] = channelsOf(stripeColour('temperature', stripeClass))
      expect(b).toBeGreaterThan(r)
    }
    for (let stripeClass = 8; stripeClass < 16; stripeClass++) {
      const [r, , b] = channelsOf(stripeColour('temperature', stripeClass))
      expect(r).toBeGreaterThan(b)
    }
  })

  it('is the ColorBrewer Blues and Reds of 9 classes, without the palest of each', () => {
    const blues = ['#08306b', '#08519c', '#2171b5', '#4292c6', '#6baed6', '#9ecae1', '#c6dbef', '#deebf7']
    const reds = ['#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#a50f15', '#67000d']
    expect(STRIPE_PALETTES.temperature).toEqual([...blues, ...reds])
  })

  it('is the end of the scale for a class beyond it', () => {
    expect(stripeColour('temperature', -3)).toBe('#08306b')
    expect(stripeColour('temperature', 99)).toBe('#67000d')
  })
})

describe('the sentence that says what the colours are relative to', () => {
  const t = (key: string, params?: Record<string, unknown>) => `${key}${params ? JSON.stringify(params) : ''}`
  const stat = (first_year: number, last_year: number, fallback = false) => ({ first_year, last_year, fallback })

  it('names the periods of the method, and the standard deviations the scale spans', () => {
    expect(stripesReferenceText({ centre: stat(1971, 2000), spread: stat(1901, 2000), range_sigma: 2.6 }, t, value => String(value)))
      .toBe('stripes.reference{"centre":"1971–2000","spread":"1901–2000","sigma":"2.6"}')
  })

  it('names the whole record, with its years, for a period the station has too few years in', () => {
    expect(stripesReferenceText({ centre: stat(1991, 2020, true), spread: stat(1901, 2000), range_sigma: 2.6 }, t, value => String(value)))
      .toBe('stripes.reference{"centre":"stripes.referenceWhole{\\"from\\":1991,\\"to\\":2020}","spread":"1901–2000","sigma":"2.6"}')
  })
})

describe('the sentence that says what stripes show', () => {
  it('names the years it spans and the lowest and the highest year with its value', () => {
    const years = stripeYears(answer(
      ['2018-01-01T00:00:00+00:00', 8, -1, 5],
      ['2019-01-01T00:00:00+00:00', 12, 3, 12],
      ['2020-01-01T00:00:00+00:00', 9, 0, 8],
    ))
    expect(stripesSummaryParams(years, value => `${value} °C`)).toEqual({ from: 2018, to: 2020, min: '8 °C', minYear: 2018, max: '12 °C', maxYear: 2019 })
  })
})

describe('wrapChartTitle', () => {
  const title = 'Climate stripes (Temperature) for Donaueschingen (Landeplatz), Germany (00011)'
  const font = '16px Arial, sans-serif'
  // a fake measure: 8 px a character, as the estimate's 0.5 em of 16 px
  const measure = (text: string) => text.length * 8

  it('leaves a title that fits the width in one line', () => {
    expect(wrapChartTitle(title, 645, font, measure)).toEqual({ text: title, lines: 1 })
  })

  it('breaks a title at spaces into lines that fit the width', () => {
    const { text, lines } = wrapChartTitle(title, 236, font, measure)
    expect(lines).toBe(3)
    expect(text.split('<br>')).toEqual(['Climate stripes (Temperature)', 'for Donaueschingen', '(Landeplatz), Germany (00011)'])
    expect(text.split('<br>').every(line => measure(line) <= 236)).toBe(true)
    // nothing is lost or added but the breaks
    expect(text.replaceAll('<br>', ' ')).toBe(title)
  })

  it('keeps a word wider than the width, with no hyphen or slash, whole on a line of its own', () => {
    expect(wrapChartTitle('a Donaueschingen b', 40, font, measure)).toEqual({ text: 'a<br>Donaueschingen<br>b', lines: 3 })
  })

  it('breaks a word wider than the width after its hyphens and slashes, which stay at the end of the line', () => {
    const name = 'Mallersdorf-Pfaffenberg-Oberlindhart'
    const { text } = wrapChartTitle(`Climate stripes for ${name} (00011)`, 236, font, measure)
    const lines = text.split('<br>')
    expect(lines).toEqual(['Climate stripes for', 'Mallersdorf-Pfaffenberg-', 'Oberlindhart (00011)'])
    expect(lines.every(line => measure(line) <= 236)).toBe(true)
    expect(wrapChartTitle('Fichtelberg/Oberfranken-Hüttstadl', 150, font, measure).text).toBe('Fichtelberg/<br>Oberfranken-<br>Hüttstadl')
  })

  it('estimates 0.5 em a character where there is no canvas to measure with', () => {
    // the unit tests run without one
    expect(wrapChartTitle('aaaa bbbb', 40, font, () => null)).toEqual({ text: 'aaaa<br>bbbb', lines: 2 })
  })
})

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { STRIPE_CLASS_COUNT, STRIPE_CLASSES, STRIPE_PALETTES, stripeBand, stripeColour, stripesReferenceShort, stripesReferenceText, stripesSummaryParams, stripeYears, wrapChartTitle } from '../../app/utils/stripes'
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

  // the half-ramps of ColorBrewer's 11-class BrBG without its neutral middle, and the 8 colours of each side mixed in RGB along them at even
  // steps: our own choice, as Hawkins has no precipitation stripes (the port of `_sample` of the backend's `ui/stripes_scale.py`, removed by GH-4258)
  const BRBG_DRY = ['#543005', '#8c510a', '#bf812d', '#dfc27d', '#f6e8c3']
  const BRBG_WET = ['#c7eae5', '#80cdc1', '#35978f', '#01665e', '#003c30']
  function sample(anchors: string[], count = 8): string[] {
    const channels = anchors.map(anchor => [1, 3, 5].map(at => Number.parseInt(anchor.slice(at, at + 2), 16)))
    return Array.from({ length: count }, (_, step) => {
      const position = step / (count - 1) * (anchors.length - 1)
      const low = Math.min(Math.trunc(position), anchors.length - 2)
      const share = position - low
      // Python's `round` goes to the even number at a half, as `Math.round` does not
      const mixed = [0, 1, 2].map((channel) => {
        const value = channels[low]![channel]! + (channels[low + 1]![channel]! - channels[low]![channel]!) * share
        const floor = Math.floor(value)
        return value - floor === 0.5 ? (floor % 2 === 0 ? floor : floor + 1) : Math.round(value)
      })
      return `#${mixed.map(channel => channel.toString(16).padStart(2, '0')).join('')}`
    })
  }

  it('has a precipitation palette that is BrBG sampled at even steps: brown for dry, teal for wet', () => {
    expect([...sample(BRBG_DRY), ...sample(BRBG_WET)]).toEqual(STRIPE_PALETTES.precipitation)
    // the ends are ColorBrewer's own darkest brown and darkest blue-green, and the middle pair is pale on both sides
    expect([STRIPE_PALETTES.precipitation[0], STRIPE_PALETTES.precipitation[15]]).toEqual([BRBG_DRY[0], BRBG_WET[4]])
    expect([STRIPE_PALETTES.precipitation[7], STRIPE_PALETTES.precipitation[8]]).toEqual([BRBG_DRY[4], BRBG_WET[0]])
  })

  it('mixes in RGB and keeps the ends, in the sampling the palette is made by', () => {
    expect(sample(['#000000', '#ffffff'], 2)).toEqual(['#000000', '#ffffff'])
    expect(sample(['#000000', '#ffffff'], 3)).toEqual(['#000000', '#808080', '#ffffff'])
    expect(sample(['#000000', '#ff0000', '#ffffff'], 3)).toEqual(['#000000', '#ff0000', '#ffffff'])
  })

  it('has the 16 colours of the pixels of Ed Hawkins\' own graphics for the temperature, the 8 most saturated of the two palettes', () => {
    expect(new Set(STRIPE_PALETTES.temperature)).toEqual(new Set([
      '#08306b',
      '#08519c',
      '#2171b5',
      '#4292c6',
      '#6baed6',
      '#9ecae1',
      '#c6dbef',
      '#deebf7',
      '#fee0d2',
      '#fcbba1',
      '#fc9272',
      '#fb6a4a',
      '#ef3b2c',
      '#cb181d',
      '#a50f15',
      '#67000d',
    ]))
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

describe('the short line under the chart (GH-4233)', () => {
  const t = (key: string, params?: Record<string, unknown>) => `${key}${params ? JSON.stringify(params) : ''}`
  const stat = (first_year: number, last_year: number, fallback = false) => ({ first_year, last_year, fallback })

  it('names the periods the mean and the spread are from, and nothing of how the scale is made', () => {
    expect(stripesReferenceShort({ centre: stat(1971, 2000), spread: stat(1944, 2000), range_sigma: 2.6 }, t))
      .toBe('stripes.referenceShort.stripes{"centre":"1971–2000","spread":"1944–2000"}')
  })

  it('says it is the mean the bars are drawn from, for the bars', () => {
    expect(stripesReferenceShort({ centre: stat(1971, 2000), spread: stat(1901, 2000), range_sigma: 2.6 }, t, 'bars'))
      .toBe('stripes.referenceShort.bars{"centre":"1971–2000","spread":"1901–2000"}')
  })

  it.each([['stripes', 'stripes.referenceShort.stripesWhole'], ['bars', 'stripes.referenceShort.barsWhole']] as const)('says it is the station\'s whole record, with its years, where the station has too few years in both periods (%s)', (drawing, key) => {
    expect(stripesReferenceShort({ centre: stat(2001, 2020, true), spread: stat(2001, 2020, true), range_sigma: 2.6 }, t, drawing))
      .toBe(`${key}{"from":2001,"to":2020}`)
  })

  // the short line as the catalogs write it, with each placeholder filled
  const rendered = (locale: string) => {
    const messages = JSON.parse(readFileSync(join(process.cwd(), 'i18n', 'locales', `${locale}.json`), 'utf8')) as Record<string, unknown>
    return (key: string, params: Record<string, unknown> = {}) => {
      const text = key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], messages) as string
      return text.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name]))
    }
  }

  it.each([
    ['en', 'stripes', 'Relative to the mean of 1971–2000 (spread from 1944–2000)'],
    ['en', 'bars', 'Bars: the difference from the mean of 1971–2000 (spread from 1944–2000)'],
    ['de', 'stripes', 'Bezogen auf das Mittel von 1971–2000 (Streuung aus 1944–2000)'],
  ] as const)('writes the periods of the method plainly (%s, %s)', (locale, drawing, text) => {
    expect(stripesReferenceShort({ centre: stat(1971, 2000), spread: stat(1944, 2000), range_sigma: 2.6 }, rendered(locale), drawing)).toBe(text)
  })

  it.each([
    // only the mean's period has too few years in it: the whole record, in no parentheses of its own, inside the line's
    ['en', 'stripes', { centre: stat(1890, 1959, true), spread: stat(1901, 1959) }, 'Relative to the mean of the whole record, 1890–1959 (spread from 1901–1959)'],
    ['en', 'bars', { centre: stat(1890, 1959, true), spread: stat(1901, 1959) }, 'Bars: the difference from the mean of the whole record, 1890–1959 (spread from 1901–1959)'],
    ['de', 'stripes', { centre: stat(1890, 1959, true), spread: stat(1901, 1959) }, 'Bezogen auf das Mittel von der gesamten Zeitreihe, 1890–1959 (Streuung aus 1901–1959)'],
    // only the spread's: a station from 1976 has 25 years in 1971 to 2000 (20 are needed) and 25 in 1901 to 2000 (30 are)
    ['en', 'stripes', { centre: stat(1976, 2000), spread: stat(1976, 2024, true) }, 'Relative to the mean of 1976–2000 (spread from the whole record, 1976–2024)'],
    ['en', 'bars', { centre: stat(1976, 2000), spread: stat(1976, 2024, true) }, 'Bars: the difference from the mean of 1976–2000 (spread from the whole record, 1976–2024)'],
    ['fr', 'stripes', { centre: stat(1976, 2000), spread: stat(1976, 2024, true) }, 'Relatif à la moyenne de 1976–2000 (dispersion de toute la série, 1976–2024)'],
    ['pl', 'stripes', { centre: stat(1976, 2000), spread: stat(1976, 2024, true) }, 'Względem średniej z 1976–2000 (rozrzut z całego szeregu, 1976–2024)'],
    // both: one phrase, with the years once
    ['en', 'stripes', { centre: stat(2001, 2020, true), spread: stat(2001, 2020, true) }, 'Relative to the station\'s whole record, 2001–2020'],
    ['en', 'bars', { centre: stat(2001, 2020, true), spread: stat(2001, 2020, true) }, 'Bars: the difference from the mean of the station\'s whole record, 2001–2020'],
  ] as const)('writes the whole record where it stands in for one or both of the numbers (%s, %s, %#)', (locale, drawing, stats, text) => {
    const line = stripesReferenceShort({ ...stats, range_sigma: 2.6 }, rendered(locale), drawing)
    expect(line).toBe(text)
    // never a bracket inside a bracket
    expect(line).not.toMatch(/\([^)]*\(/)
  })

  it('reads the whole record\'s years from the answer, for the number that fell back', () => {
    expect(stripesReferenceShort({ centre: stat(1930, 1975, true), spread: stat(1930, 1975), range_sigma: 2.6 }, t))
      .toBe('stripes.referenceShort.stripes{"centre":"stripes.referenceShort.record{\\"from\\":1930,\\"to\\":1975}","spread":"1930–1975"}')
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

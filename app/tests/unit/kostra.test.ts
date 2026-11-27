import { describe, expect, it } from 'vitest'
import {
  cellCorners,
  durationLabel,
  KOSTRA_CURVE_COLOURS,
  KOSTRA_DURATIONS,
  KOSTRA_RETURN_PERIODS,
  linkPoint,
  parseKostra,
  pointText,
  quantityOf,
  queryOfPoint,
  roundLinkCoordinate,
} from '../../app/utils/kostra'
import { depthOf, DURATIONS, kostraAnswer, RETURN_PERIODS } from '../helpers/kostra-answer'

// The Heavy-rainfall tool's reading of DWD's design rainfall (GH-4500): the table of an answer, the labels of the durations, the point
// in the link and the cell on the map.

function t(key: string, named: Record<string, unknown> = {}) {
  return ({ 'kostra.duration.minutes': `${named.n} min`, 'kostra.duration.hours': `${named.n} h`, 'kostra.duration.days': `${named.n} d` })[key] ?? key
}

describe('the durations and return periods', () => {
  it('are the 22 and the 9 of DWD, in the order of the table', () => {
    expect([...KOSTRA_DURATIONS]).toEqual(DURATIONS)
    expect(KOSTRA_DURATIONS).toHaveLength(22)
    expect([...KOSTRA_RETURN_PERIODS]).toEqual(RETURN_PERIODS)
    expect(KOSTRA_RETURN_PERIODS).toHaveLength(9)
  })
})

describe('parseKostra', () => {
  it('reads the cell, the edition and the credit of an answer', () => {
    const table = parseKostra(kostraAnswer())!
    expect(table.cell).toEqual({ indexRc: '144197', latitude: 50.747211, longitude: 13.777738 })
    expect(table.edition).toBe('KOSTRA-DWD-2020')
    expect(table.credit?.attribution).toBe('Source: Deutscher Wetterdienst')
    expect(table.credit?.license?.name).toBe('CC BY 4.0')
  })

  it('puts every value in the row of its duration and the column of its return period', () => {
    const table = parseKostra(kostraAnswer())!
    expect(table.rows).toHaveLength(22)
    expect(table.rows.every(row => row.length === 9)).toBe(true)
    // 1 h is the 7th duration, 100 years the 9th period
    const entry = table.rows[KOSTRA_DURATIONS.indexOf(60)]![KOSTRA_RETURN_PERIODS.indexOf(100)]!
    expect(entry.depthMm).toBe(depthOf(60, 100))
    expect(entry.intensity).toBeCloseTo(depthOf(60, 100) / 60 * 10000 / 60, 0)
    expect(entry.uncertaintyPercent).toBe(12)
  })

  it('keeps a value DWD gives none for as a gap, not a zero', () => {
    const table = parseKostra(kostraAnswer({ missing: [[60, 100]] }))!
    const row = table.rows[KOSTRA_DURATIONS.indexOf(60)]!
    expect(row[8]).toEqual({ depthMm: null, intensity: null, uncertaintyPercent: null })
    expect(quantityOf(row[8]!, 'depth')).toBeNull()
    expect(quantityOf(row[7]!, 'depth')).toBe(depthOf(60, 50))
  })

  it('leaves out a value for a duration or a return period DWD does not give, and reads a table with holes', () => {
    const answer = kostraAnswer()
    answer.values = [
      { duration_minutes: 7, return_period_years: 1, depth_mm: 1, intensity_l_s_ha: 1, uncertainty_percent: 1 },
      { duration_minutes: 5, return_period_years: 4, depth_mm: 1, intensity_l_s_ha: 1, uncertainty_percent: 1 },
      answer.values[0]!,
    ]
    const table = parseKostra(answer)!
    expect(table.rows.flat().filter(entry => entry !== null)).toHaveLength(1)
    expect(table.rows[0]![0]!.depthMm).toBe(depthOf(5, 1))
  })

  it.each([
    ['nothing', null],
    ['a text, as a proxy\'s page is', '<html></html>'],
    ['an answer with no cell', { values: [] }],
    ['an answer with no values', { cell: { index_rc: '1', latitude: 50, longitude: 10 } }],
    ['a cell with no centre', { cell: { index_rc: '1' }, values: [] }],
  ])('is not a table: %s', (_what, answer) => {
    expect(parseKostra(answer)).toBeNull()
  })
})

describe('quantityOf', () => {
  it('is the depth or the intensity of an entry, and nothing of no entry', () => {
    const entry = { depthMm: 12.5, intensity: 41.7, uncertaintyPercent: 11 }
    expect(quantityOf(entry, 'depth')).toBe(12.5)
    expect(quantityOf(entry, 'intensity')).toBe(41.7)
    expect(quantityOf(null, 'depth')).toBeNull()
  })
})

describe('durationLabel', () => {
  it('writes minutes under an hour, and where the minutes are not a whole number of hours', () => {
    expect(durationLabel(5, t)).toBe('5 min')
    expect(durationLabel(45, t)).toBe('45 min')
    expect(durationLabel(90, t)).toBe('90 min')
  })

  it('writes a whole number of hours under a day in h', () => {
    expect(durationLabel(60, t)).toBe('1 h')
    expect(durationLabel(120, t)).toBe('2 h')
    expect(durationLabel(540, t)).toBe('9 h')
    expect(durationLabel(720, t)).toBe('12 h')
  })

  it('writes a whole number of days in d', () => {
    expect(durationLabel(1440, t)).toBe('1 d')
    expect(durationLabel(4320, t)).toBe('3 d')
    expect(durationLabel(10080, t)).toBe('7 d')
  })

  it('gives every one of the 22 durations a label of its own', () => {
    const labels = KOSTRA_DURATIONS.map(minutes => durationLabel(minutes, t))
    expect(new Set(labels).size).toBe(22)
    expect(labels).toEqual(['5 min', '10 min', '15 min', '20 min', '30 min', '45 min', '1 h', '90 min', '2 h', '3 h', '4 h', '6 h', '9 h', '12 h', '18 h', '1 d', '2 d', '3 d', '4 d', '5 d', '6 d', '7 d'])
  })
})

describe('the point in the link', () => {
  it('is read from lat and lon', () => {
    expect(linkPoint({ lat: '50.7313', lon: '13.7516' })).toEqual({ latitude: 50.7313, longitude: 13.7516 })
    expect(linkPoint({ lat: '-33.87', lon: '-151.2' })).toEqual({ latitude: -33.87, longitude: -151.2 })
    // the first of a repeated parameter
    expect(linkPoint({ lat: ['50.1', '51'], lon: ['8.7'] })).toEqual({ latitude: 50.1, longitude: 8.7 })
  })

  it.each([
    ['no point', {}],
    ['a latitude alone', { lat: '50' }],
    ['a longitude alone', { lon: '8' }],
    ['text', { lat: 'north', lon: 'east' }],
    ['empty values', { lat: '', lon: ' ' }],
    ['a latitude beyond 90', { lat: '91', lon: '8' }],
    ['a longitude beyond 180', { lat: '50', lon: '181' }],
    ['infinity', { lat: '1e999', lon: '8' }],
  ])('is none for %s', (_what, query) => {
    expect(linkPoint(query)).toBeNull()
  })

  it('goes round: a point written to the link is the point read from it, to its four decimals', () => {
    const point = { latitude: 50.731299, longitude: 13.751601 }
    const query = queryOfPoint(point)
    expect(query).toEqual({ lat: '50.7313', lon: '13.7516' })
    expect(linkPoint(query)).toEqual({ latitude: 50.7313, longitude: 13.7516 })
    // and what is read from a link is written back as it was
    expect(queryOfPoint(linkPoint(query)!)).toEqual(query)
  })

  it('is written with a point and never in exponent form', () => {
    expect(queryOfPoint({ latitude: 0.00001, longitude: -0.00004 })).toEqual({ lat: '0', lon: '0' })
    expect(queryOfPoint({ latitude: 1e-7, longitude: 52.00005 })).toEqual({ lat: '0', lon: '52.0001' })
    expect(roundLinkCoordinate(13.75155)).toBe(13.7516)
    expect(pointText({ latitude: 50.7, longitude: 13.75 })).toBe('50.7000, 13.7500')
  })
})

describe('the cell on the map', () => {
  /** The distance between two points, in metres (haversine) */
  const distance = (a: [number, number], b: [number, number]) => {
    const rad = (x: number) => x * Math.PI / 180
    const h = Math.sin(rad(b[0] - a[0]) / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(rad(b[1] - a[1]) / 2) ** 2
    return 2 * 6_371_007 * Math.asin(Math.sqrt(h))
  }
  const centre = { latitude: 50.747211, longitude: 13.777738 }

  it('is four corners of a square 5 km wide (to a few metres: the corners are drawn on a sphere)', () => {
    const corners = cellCorners(centre)
    expect(corners).toHaveLength(4)
    for (let i = 0; i < 4; i++)
      expect(distance(corners[i]!, corners[(i + 1) % 4]!)).toBeGreaterThan(4950)
    for (let i = 0; i < 4; i++)
      expect(distance(corners[i]!, corners[(i + 1) % 4]!)).toBeLessThan(5050)
    // and the diagonals are 5 km times the square root of two
    expect(distance(corners[0]!, corners[2]!)).toBeCloseTo(5000 * Math.SQRT2, -2)
  })

  it('has the centre of the cell in the middle of its corners', () => {
    const corners = cellCorners(centre)
    const mean = (index: 0 | 1) => corners.reduce((sum, corner) => sum + corner[index], 0) / 4
    expect(mean(0)).toBeCloseTo(centre.latitude, 3)
    expect(mean(1)).toBeCloseTo(centre.longitude, 3)
  })

  it('is turned a little off north where the grid is: the grid is aligned to 10 E, so at 13.8 E the north edge is not level', () => {
    const [northWest, northEast] = cellCorners(centre)
    expect(northWest![0]).not.toBeCloseTo(northEast![0], 4)
    // at the grid's own meridian it is level
    const [west, east] = cellCorners({ latitude: 52, longitude: 10 })
    expect(west![0]).toBeCloseTo(east![0], 5)
  })
})

describe('the colours of the curves', () => {
  const luminance = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16) / 255).map(c => c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4) as [number, number, number]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  const contrast = (a: string, b: string) => (Math.max(luminance(a), luminance(b)) + 0.05) / (Math.min(luminance(a), luminance(b)) + 0.05)

  it('are nine, one for each return period, in each scheme', () => {
    expect(KOSTRA_CURVE_COLOURS.light).toHaveLength(9)
    expect(KOSTRA_CURVE_COLOURS.dark).toHaveLength(9)
  })

  it.each([
    ['by day, on the white of a card', 'light' as const, '#ffffff'],
    ['at night, on the dark card (--ui-bg)', 'dark' as const, '#12233f'],
  ])('clear 3:1 against the paper they are drawn on, %s (WCAG 1.4.11)', (_when, scheme, paper) => {
    for (const colour of KOSTRA_CURVE_COLOURS[scheme])
      expect(contrast(colour, paper), colour).toBeGreaterThanOrEqual(3)
  })

  it('go from light to dark by day and from dark to light at night: the longer the return period, the stronger the line', () => {
    const light = KOSTRA_CURVE_COLOURS.light.map(luminance)
    const dark = KOSTRA_CURVE_COLOURS.dark.map(luminance)
    expect([...light].sort((a, b) => b - a)).toEqual(light)
    expect([...dark].sort((a, b) => a - b)).toEqual(dark)
  })
})

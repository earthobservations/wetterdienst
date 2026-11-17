import type { StripesInput, StripesReferenceInput } from '../../app/utils/stripes-model'
import { describe, expect, it } from 'vitest'
import { availabilityRuns, buildStripesModel, clampWindow, fullWindow, MIN_SPAN_STRIPES, panWindow, revealYear, sameWindow, visibleYears, zoomWindow } from '../../app/utils/stripes-model'
import { recordOf, stripesAnswer } from '../helpers/stripes-answer'

// a reference with its centre at 10 and 1 standard deviation: the scale reaches from 7.4 to 12.6
const REFERENCE: StripesReferenceInput = { centre: { value: 10 }, spread: { value: 1 }, range_sigma: 2.6 }
const input = (timestamp: string | null, value: number | null, anomaly: number | null = null, stripe_class: number | null = null): StripesInput => ({ timestamp, value, anomaly, stripe_class })

function answer(years: number[], value = (year: number) => year / 100) {
  const items = stripesAnswer(years.map(year => ({ year, value: value(year) })))
  return { values: items.values, reference: items.reference }
}

describe('buildStripesModel', () => {
  it('has no model where nothing can be drawn', () => {
    expect(buildStripesModel([], REFERENCE)).toBeNull()
    expect(buildStripesModel([input('2000-01-01T00:00:00+00:00', null), input(null, 3, 0, 8)], REFERENCE)).toBeNull()
  })

  it('reads each year in UTC, from the years with a value, with the anomaly and class the answer gives them', () => {
    const model = buildStripesModel([
      input('2001-01-01T00:00:00+00:00', 10, 0, 8),
      input('2002-01-01T00:00:00+00:00', null),
      input('2003-01-01T00:00:00+00:00', 11, 1, 11),
      input('2004-01-01T00:00:00+00:00', 9, -1, 4),
    ], REFERENCE)!
    expect(model.years).toEqual([2001, 2003, 2004])
    expect(model.classes).toEqual([8, 11, 4])
    expect(model.anomalies).toEqual([0, 1, -1])
    expect([model.minYear, model.maxYear]).toEqual([2001, 2004])
    // the availability line is broken where a year has no value
    expect(model.availability).toEqual([-0.02, null, -0.02, -0.02])
  })

  it('places the values on the scale of the reference: the centre in the middle, 2.6 standard deviations at an edge', () => {
    const model = buildStripesModel([
      input('2001-01-01T00:00:00+00:00', 10, 0, 8),
      input('2002-01-01T00:00:00+00:00', 12.6, 2.6, 15),
      input('2003-01-01T00:00:00+00:00', 7.4, -2.6, 0),
      input('2004-01-01T00:00:00+00:00', 11.3, 1.3, 12),
    ], REFERENCE)!
    expect(model.normalized.map(value => Math.round(value * 1e9) / 1e9)).toEqual([0.5, 1, 0, 0.75])
  })

  it('puts a value beyond the scale on its edge, as its stripe is in the end class', () => {
    const model = buildStripesModel([input('2001-01-01T00:00:00+00:00', 40, 30, 15), input('2002-01-01T00:00:00+00:00', -20, -30, 0)], REFERENCE)!
    expect(model.normalized).toEqual([1, 0])
    expect(model.classes).toEqual([15, 0])
  })

  it('does not place a value by the years shown: a window of the record leaves the lines where the whole record has them', () => {
    const record = recordOf(1950, 2020, year => 8 + (year - 1950) * 0.04 + (year % 2 ? 0.3 : -0.3))
    const whole = stripesAnswer(record)
    const window = stripesAnswer(record, { start: 2005, end: 2015 })
    const modelOf = (data: typeof whole) => buildStripesModel(data.values, data.reference)!
    const all = modelOf(whole)
    const part = modelOf(window)
    expect(part.years).toEqual(Array.from({ length: 11 }, (_, index) => 2005 + index))
    expect(part.classes).toEqual(all.classes.slice(all.years.indexOf(2005), all.years.indexOf(2015) + 1))
    expect(part.normalized).toEqual(all.normalized.slice(all.years.indexOf(2005), all.years.indexOf(2015) + 1))
  })

  it('puts years of no spread in the middle of the scale, not at NaN', () => {
    const model = buildStripesModel([input('2000-01-01T00:00:00+00:00', 7, 0, 8), input('2001-01-01T00:00:00+00:00', 7, 0, 8)], { centre: { value: 7 }, spread: { value: 0 }, range_sigma: 2.6 })!
    expect(model.normalized).toEqual([0.5, 0.5])
    expect(model.normalizedTrend.every(Number.isFinite)).toBe(true)
  })

  it('draws the least-squares line through the years, on the same scale', () => {
    const items = [2000, 2001, 2002, 2003].map((year, index) => input(`${year}-01-01T00:00:00+00:00`, 9 + index, -1 + index, 4 + index * 3))
    const model = buildStripesModel(items, REFERENCE)!
    expect(model.trend.map(value => Math.round(value * 1e6) / 1e6)).toEqual([9, 10, 11, 12])
    // 1 standard deviation is 1 / 5.2 of the scale
    expect(model.normalizedTrend.map(value => Math.round(value * 1e6) / 1e6)).toEqual([0.5 - 1 / 5.2, 0.5, 0.5 + 1 / 5.2, 0.5 + 2 / 5.2].map(value => Math.round(value * 1e6) / 1e6))
  })

  it('does not divide by nothing for a single year', () => {
    const model = buildStripesModel([input('2000-01-01T00:00:00+00:00', 20, 10, 15)], REFERENCE)!
    expect(model.trend).toEqual([20])
  })

  it('draws the classes of a long record as the backend would give them', () => {
    const data = answer(Array.from({ length: 120 }, (_, index) => 1901 + index), year => 8 + (year - 1901) * 0.02)
    const model = buildStripesModel(data.values, data.reference)!
    // warming from below the mean of 1971 to 2000 to above it, with the classes rising with it
    expect(model.classes[0]).toBe(0)
    expect(model.classes.at(-1)).toBeGreaterThan(8)
    expect(model.classes).toEqual([...model.classes].sort((a, b) => a - b))
  })
})

describe('the window of years', () => {
  const model = { minYear: 1950, maxYear: 2024 }
  const bounds = fullWindow(model)

  it('is the whole chart to start with: a stripe is its year plus and minus a half', () => {
    expect(bounds).toEqual({ start: 1949.5, end: 2024.5 })
  })

  it('zooms round an anchor that keeps its place, and stops at the least and the most', () => {
    const zoomed = zoomWindow(bounds, 0.5, 2000, bounds)
    expect(zoomed.end - zoomed.start).toBeCloseTo(37.5)
    expect(zoomed.start <= 2000 && zoomed.end >= 2000).toBe(true)
    expect(zoomWindow(bounds, 2, 2000, bounds)).toEqual(bounds)
    const tight = zoomWindow({ start: 2000, end: 2004 }, 0.01, 2002, bounds)
    expect(tight.end - tight.start).toBe(MIN_SPAN_STRIPES)
  })

  it('pans within the bounds and keeps its width', () => {
    const win = { start: 1960, end: 1980 }
    expect(panWindow(win, 10, bounds)).toEqual({ start: 1970, end: 1990 })
    expect(panWindow(win, -100, bounds)).toEqual({ start: 1949.5, end: 1969.5 })
    expect(panWindow(win, 100, bounds)).toEqual({ start: 2004.5, end: 2024.5 })
  })

  it('moves the least that shows a stripe', () => {
    const win = { start: 1960, end: 1980 }
    expect(revealYear(win, 1970, bounds)).toBe(win)
    expect(revealYear(win, 1990, bounds)).toEqual({ start: 1970.5, end: 1990.5 })
    expect(revealYear(win, 1950, bounds)).toEqual({ start: 1949.5, end: 1969.5 })
  })

  it('names the first and the last stripe whose middle is in it', () => {
    expect(visibleYears(bounds, model)).toEqual([1950, 2024])
    expect(visibleYears({ start: 1960, end: 1980 }, model)).toEqual([1960, 1980])
    expect(visibleYears({ start: 1959.5, end: 1979.5 }, model)).toEqual([1960, 1979])
  })

  it('names a year that has a stripe at either end, not one in a gap', () => {
    const years = Array.from({ length: 75 }, (_, i) => 1950 + i).filter(year => year < 1962 || year > 1964)
    const full = { minYear: 1950, maxYear: 2024, years }
    // starts at 1961.6: the stripe of 1962 is not there, and the first that is is 1965; ends in the gap the same way
    expect(visibleYears({ start: 1961.6, end: 1990.5 }, full)).toEqual([1965, 1990])
    expect(visibleYears({ start: 1955.5, end: 1963.4 }, full)).toEqual([1956, 1961])
    // a window with no stripe in it names the years it reaches
    expect(visibleYears({ start: 1961.6, end: 1964.4 }, full)).toEqual([1962, 1964])
    // and years in any order
    expect(visibleYears({ start: 1960, end: 1970 }, { ...full, years: [...years].reverse() })).toEqual([1960, 1970])
  })

  it('clamps a window into the bounds', () => {
    expect(clampWindow({ start: 1900, end: 1910 }, bounds)).toEqual({ start: 1949.5, end: 1959.5 })
    expect(clampWindow({ start: 1900, end: 2100 }, bounds)).toEqual(bounds)
  })

  it('tells windows apart by a hundredth of a year', () => {
    expect(sameWindow({ start: 1, end: 2 }, { start: 1.001, end: 2 })).toBe(true)
    expect(sameWindow({ start: 1, end: 2 }, { start: 1.1, end: 2 })).toBe(false)
  })
})

describe('availabilityRuns (GH-4153)', () => {
  /** The runs of the years of an answer that has a value for `years` */
  const runsOf = (years: number[]) => {
    const data = answer(years)
    const model = buildStripesModel(data.values, data.reference)!
    return availabilityRuns(model.availability, model.minYear)
  }

  it('is one run for years without a gap', () => {
    expect(runsOf([2000, 2001, 2002, 2003])).toEqual([{ first: 2000, last: 2003 }])
    expect(runsOf([2000])).toEqual([{ first: 2000, last: 2000 }])
  })

  it('has a run of one year for a lone year at the start, in the middle and at the end', () => {
    // 1944, a gap, a run, a gap, a lone year, a gap, a run of two (the shape of the station of GH-4153), then a lone year at the end
    expect(runsOf([1944, 1946, 1947, 1948, 1950, 1952, 1953, 1955])).toEqual([
      { first: 1944, last: 1944 },
      { first: 1946, last: 1948 },
      { first: 1950, last: 1950 },
      { first: 1952, last: 1953 },
      { first: 1955, last: 1955 },
    ])
  })

  it('has a run of two years that is two stripes wide, not a point', () => {
    expect(runsOf([2000, 2001, 2003])).toEqual([{ first: 2000, last: 2001 }, { first: 2003, last: 2003 }])
  })

  it('has one run of one year where only one year has a value among years that have none', () => {
    const availability = [null, null, -0.02, null, null]
    expect(availabilityRuns(availability, 1990)).toEqual([{ first: 1992, last: 1992 }])
  })

  it('has no run where no year has a value, and tells every gap of years from a run (a gap of one year splits two runs)', () => {
    expect(availabilityRuns([], 2000)).toEqual([])
    expect(availabilityRuns([null, null], 2000)).toEqual([])
    expect(availabilityRuns([-0.02, null, -0.02], 2000)).toEqual([{ first: 2000, last: 2000 }, { first: 2002, last: 2002 }])
  })
})

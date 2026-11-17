import type { StripesInput } from '../../app/utils/stripes-model'
import { describe, expect, it } from 'vitest'
import { anomalyAxis, availabilityRuns, buildStripesModel, clampWindow, fullWindow, MIN_SPAN_STRIPES, panWindow, revealYear, sameWindow, visibleYears, yearTicks, zoomWindow } from '../../app/utils/stripes-model'
import { recordOf, stripesAnswer } from '../helpers/stripes-answer'

const input = (timestamp: string | null, value: number | null, anomaly: number | null = null, stripe_class: number | null = null): StripesInput => ({ timestamp, value, anomaly, stripe_class })

function answer(years: number[], value = (year: number) => year / 100) {
  const items = stripesAnswer(years.map(year => ({ year, value: value(year) })))
  return { values: items.values, reference: items.reference }
}

describe('buildStripesModel', () => {
  it('has no model where nothing can be drawn', () => {
    expect(buildStripesModel([])).toBeNull()
    expect(buildStripesModel([input('2000-01-01T00:00:00+00:00', null), input(null, 3, 0, 8)])).toBeNull()
  })

  it('reads each year in UTC, from the years with a value, with the anomaly and class the answer gives them', () => {
    const model = buildStripesModel([
      input('2001-01-01T00:00:00+00:00', 10, 0, 8),
      input('2002-01-01T00:00:00+00:00', null),
      input('2003-01-01T00:00:00+00:00', 11, 1, 11),
      input('2004-01-01T00:00:00+00:00', 9, -1, 4),
    ])!
    expect(model.years).toEqual([2001, 2003, 2004])
    expect(model.classes).toEqual([8, 11, 4])
    expect(model.anomalies).toEqual([0, 1, -1])
    expect([model.minYear, model.maxYear]).toEqual([2001, 2004])
    // the availability line is broken where a year has no value
    expect(model.availability).toEqual([-0.02, null, -0.02, -0.02])
  })

  it('does not class a year by the years shown: a window of the record leaves each year its class', () => {
    const record = recordOf(1950, 2020, year => 8 + (year - 1950) * 0.04 + (year % 2 ? 0.3 : -0.3))
    const whole = stripesAnswer(record)
    const window = stripesAnswer(record, { start: 2005, end: 2015 })
    const modelOf = (data: typeof whole) => buildStripesModel(data.values)!
    const all = modelOf(whole)
    const part = modelOf(window)
    expect(part.years).toEqual(Array.from({ length: 11 }, (_, index) => 2005 + index))
    expect(part.classes).toEqual(all.classes.slice(all.years.indexOf(2005), all.years.indexOf(2015) + 1))
    expect(part.anomalies).toEqual(all.anomalies.slice(all.years.indexOf(2005), all.years.indexOf(2015) + 1))
  })

  it('draws the classes of a long record as the backend would give them', () => {
    const data = answer(Array.from({ length: 120 }, (_, index) => 1901 + index), year => 8 + (year - 1901) * 0.02)
    const model = buildStripesModel(data.values)!
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

describe('anomalyAxis (GH-4156)', () => {
  it('runs from the lowest to the highest anomaly rounded out to a round step, zero in it', () => {
    const axis = anomalyAxis([-1.7, 0.3, 2.04, -0.6])
    expect(axis).toMatchObject({ min: -2, max: 3, step: 1, decimals: 0 })
    expect(axis.ticks).toEqual([-2, -1, 0, 1, 2, 3])
    // a step of a half is written with a decimal
    const fine = anomalyAxis([-0.7, 1.2, 0.1])
    expect(fine).toMatchObject({ min: -1, max: 1.5, step: 0.5, decimals: 1 })
    expect(fine.ticks).toEqual([-1, -0.5, 0, 0.5, 1, 1.5])
  })

  it('has about five intervals whatever the unit: millimetres of precipitation step in hundreds and need no decimals', () => {
    const axis = anomalyAxis([-310, 250, 40])
    expect(axis).toMatchObject({ min: -400, max: 400, step: 200, decimals: 0 })
    expect(axis.ticks).toEqual([-400, -200, 0, 200, 400])
  })

  it('takes zero as an end where the anomalies are all on one side of it', () => {
    expect(anomalyAxis([0.4, 1.1, 2.2])).toMatchObject({ min: 0, max: 2.5 })
    expect(anomalyAxis([-0.4, -1.1])).toMatchObject({ min: -1.5, max: 0 })
  })

  it('still has a range where every anomaly is nought', () => {
    const axis = anomalyAxis([0, 0])
    expect(axis.max).toBeGreaterThan(axis.min)
    expect(axis.ticks).toContain(0)
  })

  it('writes a step below a tenth with the decimals it needs', () => {
    expect(anomalyAxis([-0.03, 0.04]).decimals).toBe(2)
    expect(anomalyAxis([-0.03, 0.04]).step).toBeCloseTo(0.02)
  })
})

describe('yearTicks (GH-4156)', () => {
  it('names the multiples of ten in a record of seventy-five years on a phone and a desktop', () => {
    expect(yearTicks({ start: 1949.5, end: 2024.5 }, 664)).toEqual([1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020])
    // a narrower plot makes the step coarser, never a label on top of another
    expect(yearTicks({ start: 1949.5, end: 2024.5 }, 320)).toEqual([1960, 1980, 2000, 2020])
  })

  it('names a year only where the middle of its bar is in the window', () => {
    // 2020 is the middle of a bar that ends at 2020.5, which is the window's end: in; 1950 ends at 1950.5: out
    expect(yearTicks({ start: 1950.5, end: 2020.5 }, 600)).toEqual([1960, 1970, 1980, 1990, 2000, 2010, 2020])
  })

  it('gets finer as the window is zoomed in, down to every year', () => {
    expect(yearTicks({ start: 1999.5, end: 2020.5 }, 664)).toEqual([2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020])
    const zoomed = yearTicks({ start: 2009.5, end: 2019.5 }, 664)
    expect(zoomed).toEqual([2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019])
  })

  it('is empty where there is no window or no room', () => {
    expect(yearTicks({ start: 2000, end: 2000 }, 600)).toEqual([])
    expect(yearTicks({ start: 1950, end: 2000 }, 0)).toEqual([])
  })
})

describe('availabilityRuns (GH-4153)', () => {
  /** The runs of the years of an answer that has a value for `years` */
  const runsOf = (years: number[]) => {
    const data = answer(years)
    const model = buildStripesModel(data.values)!
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

import { describe, expect, it } from 'vitest'
import { classifyPrecip, extremeWindowHours, extremeWindowSteps, findNearestIndex, interpSeries, METEOGRAM_SERIES, wetBulbApprox } from '../../app/utils/meteogram'
import { parameters } from '../../i18n/glossary/en'

describe('findNearestIndex', () => {
  const dates = [
    new Date('2024-01-01T00:00:00Z'),
    new Date('2024-01-01T06:00:00Z'),
    new Date('2024-01-01T12:00:00Z'),
    new Date('2024-01-01T18:00:00Z'),
    new Date('2024-01-02T00:00:00Z'),
  ]

  it('returns 0 for timestamp before first date', () => {
    const target = new Date('2023-12-31T12:00:00Z').getTime()
    expect(findNearestIndex(dates, target)).toBe(0)
  })

  it('returns last index for timestamp after last date', () => {
    const target = new Date('2024-01-02T12:00:00Z').getTime()
    expect(findNearestIndex(dates, target)).toBe(dates.length - 1)
  })

  it('returns exact index when timestamp matches', () => {
    const target = new Date('2024-01-01T12:00:00Z').getTime()
    expect(findNearestIndex(dates, target)).toBe(2)
  })

  it('returns nearest index when between two dates', () => {
    const target = new Date('2024-01-01T05:00:00Z').getTime()
    const result = findNearestIndex(dates, target)
    expect([0, 1]).toContain(result)
  })

  it('returns -1 for empty array', () => {
    expect(findNearestIndex([], 1000)).toBe(-1)
  })
})

describe('interpSeries', () => {
  const dates = [
    new Date('2024-01-01T00:00:00Z'),
    new Date('2024-01-01T06:00:00Z'),
    new Date('2024-01-01T12:00:00Z'),
  ]
  const values = [10, 20, 30]

  it('returns first value for timestamp before first date', () => {
    const target = new Date('2023-12-31T12:00:00Z').getTime()
    expect(interpSeries(dates, values, target)).toBe(10)
  })

  it('returns last value for timestamp after last date', () => {
    const target = new Date('2024-01-01T18:00:00Z').getTime()
    expect(interpSeries(dates, values, target)).toBe(30)
  })

  it('returns exact value when timestamp matches', () => {
    const target = new Date('2024-01-01T06:00:00Z').getTime()
    expect(interpSeries(dates, values, target)).toBe(20)
  })

  it('interpolates between two values', () => {
    // Halfway between 00:00 (10) and 06:00 (20) = 03:00, should be 15
    const target = new Date('2024-01-01T03:00:00Z').getTime()
    const result = interpSeries(dates, values, target)
    expect(result).toBe(15)
  })

  it('handles null or undefined values gracefully', () => {
    const datesWithNull = [dates[0], dates[1], dates[2]]
    const valuesWithNull = [10, undefined as any, 30]
    // When the middle value is undefined, we still interpolate using the surrounding values
    const target = new Date('2024-01-01T03:00:00Z').getTime()
    const result = interpSeries(datesWithNull, valuesWithNull, target)
    // Should interpolate between 10 and undefined -> returns first valid value
    expect(result).toBe(10)
  })

  it('returns null for empty array', () => {
    expect(interpSeries([], [], 1000)).toBeNull()
  })
})

describe('wetBulbApprox', () => {
  it('returns reasonable values for typical conditions', () => {
    // At 20°C and 60% RH, wet-bulb should be lower than temperature
    const result = wetBulbApprox(20, 60)
    expect(result).toBeLessThan(20)
    expect(result).toBeGreaterThan(0)
  })

  it('returns approximately same as temperature at 100% RH', () => {
    const result = wetBulbApprox(20, 100)
    expect(result).toBeCloseTo(20, 1)
  })

  it('handles low humidity (dry air)', () => {
    const result = wetBulbApprox(30, 20)
    expect(result).toBeLessThan(30)
  })

  it('handles negative temperatures', () => {
    const result = wetBulbApprox(-10, 80)
    expect(result).toBeLessThan(-10)
  })
})

describe('classifyPrecip', () => {
  it('classifies as snow when T <= 0.5°C', () => {
    expect(classifyPrecip(0)).toBe('snow')
    expect(classifyPrecip(-5)).toBe('snow')
  })

  it('classifies as mixed when 0.5 < T <= 2.0', () => {
    expect(classifyPrecip(1)).toBe('mixed')
    expect(classifyPrecip(1.5)).toBe('mixed')
  })

  it('classifies as rain when T > 2.0', () => {
    expect(classifyPrecip(5)).toBe('rain')
    expect(classifyPrecip(25)).toBe('rain')
  })

  it('refines classification using wet-bulb when humidity provided', () => {
    // At 5°C with 90% RH, wet-bulb is high, so classified as rain
    const result = classifyPrecip(5, 90)
    expect(result).toBe('rain')

    // At 0°C with 90% RH, wet-bulb is low, so classified as snow/mixed
    const result2 = classifyPrecip(0, 90)
    expect(['snow', 'mixed']).toContain(result2)
  })

  it('normalizes humidity from 0-1 range to 0-100', () => {
    // Same result whether RH is 0.5 (50%) or 50
    const result1 = classifyPrecip(5, 0.5)
    const result2 = classifyPrecip(5, 50)
    expect(result1).toBe(result2)
  })
})

describe('meteogram series names', () => {
  // The English glossary is keyed by every canonical parameter name, no more and no fewer:
  // tests/e2e/i18n-coverage.spec.ts holds it to the backend's /api/glossary both ways. So a first
  // choice missing from it is a name the backend does not serve, and its series would never draw.
  it('leads every series with a canonical parameter name', () => {
    const notCanonical = Object.entries(METEOGRAM_SERIES)
      .filter(([, names]) => !Object.hasOwn(parameters, names[0]))
      .map(([series, names]) => `${series}: ${names[0]}`)
    expect(notCanonical, 'meteogram series whose first choice is not a canonical parameter').toEqual([])
  })

  // the backend names MOSMIX air temperature and dew point for a reading at one moment (GH-2657); an
  // older backend still serves the `_mean_` names, so those stay as the fallback behind them
  it('draws the MOSMIX temperature and dew point under the spot names, and the older mean names', () => {
    expect(METEOGRAM_SERIES.temperature.slice(0, 2)).toEqual(['temperature_air_2m', 'temperature_air_mean_2m'])
    expect(METEOGRAM_SERIES.dewPoint.slice(0, 2)).toEqual(['temperature_dew_point_2m', 'temperature_dew_point_mean_2m'])
  })
})

describe('extremeWindowHours', () => {
  it('reads the window from the name, 12 hours where it names none', () => {
    expect(extremeWindowHours('temperature_air_max_2m_last_12h')).toBe(12)
    expect(extremeWindowHours('temperature_air_min_2m_last_6h')).toBe(6)
    expect(extremeWindowHours('tx6')).toBe(6)
    expect(extremeWindowHours('tn12')).toBe(12)
    expect(extremeWindowHours('tx')).toBe(12)
    expect(extremeWindowHours('temperature_air_max_2m')).toBe(12)
  })
})

// dwd/mosmix, station 10147 (Hamburg-Fuhlsbuettel), the run of 2026-10-15 04:00 UTC, as /api/values
// answered the meteogram's request: the temperature of each hour from 04:00 on the 15th to 06:00 on
// the 16th, and the `tx` and `tn` DWD stamps at 06:00 and 18:00, each the extreme of the 12 hours
// before it
describe('extremeWindowSteps', () => {
  const HOUR = 3_600_000
  const start = Date.parse('2026-10-15T04:00:00Z')
  const hours = Array.from({ length: 27 }, (_, i) => new Date(start + i * HOUR))
  const temperature = [8.2, 8.3, 8.7, 9.7, 10.9, 12.5, 13.8, 15.1, 16.0, 16.5, 16.7, 16.5, 15.7, 14.6, 13.8, 13.3, 12.7, 12.6, 12.5, 12.6, 12.6, 12.5, 12.6, 12.6, 12.6, 12.8, 13.1]
  const stamps = ['2026-10-15T06:00:00Z', '2026-10-15T18:00:00Z', '2026-10-16T06:00:00Z'].map(stamp => new Date(stamp))
  const maxima = [10.3, 17.4, 13.9]
  const minima = [6.5, 8.0, 11.6]
  const from = hours[0]!.getTime()
  const to = hours[hours.length - 1]!.getTime()

  interface Steps { x: Date[], y: (number | null)[] }

  // the bound a step series holds at an hour, as a hover reads it: the one point of that date
  function heldAt(steps: Steps, hour: Date) {
    const at = steps.x.flatMap((x, i) => x.getTime() === hour.getTime() ? [steps.y[i]] : [])
    expect(at.length, `${hour.toISOString()} has more than one point`).toBeLessThanOrEqual(1)
    return at[0]
  }

  it('holds each extreme across the 12 hours before its stamp, and the temperature stays inside', () => {
    const highs = extremeWindowSteps(stamps, maxima, 12 * HOUR, from, to, HOUR)
    const lows = extremeWindowSteps(stamps, minima, 12 * HOUR, from, to, HOUR)
    for (const [i, hour] of hours.entries()) {
      expect(temperature[i]!, `${hour.toISOString()} above its maximum`).toBeLessThanOrEqual(heldAt(highs, hour)!)
      expect(temperature[i]!, `${hour.toISOString()} below its minimum`).toBeGreaterThanOrEqual(heldAt(lows, hour)!)
    }
    expect(heldAt(highs, hours[10]!)).toBe(17.4)
    expect(heldAt(lows, hours[10]!)).toBe(8.0)
  })

  it('is what the band was not: a line between the stamps lets the curve out of it', () => {
    // 14:00 UTC, 16.7 degrees, above what a line between the stamps gives there (14.1), under the
    // maximum of 17.4 that its window holds
    const afternoon = hours[10]!
    const drawnBefore = interpSeries(stamps, maxima, afternoon.getTime())!
    expect(temperature[10]).toBeGreaterThan(drawnBefore)
    expect(temperature[10]).toBeLessThanOrEqual(heldAt(extremeWindowSteps(stamps, maxima, 12 * HOUR, from, to, HOUR), afternoon)!)
  })

  it('cuts the first window off where the chart starts, and reads the window that ends at a stamp there', () => {
    const highs = extremeWindowSteps(stamps, maxima, 12 * HOUR, from, to, HOUR)
    expect(highs.x[0]!.toISOString()).toBe('2026-10-15T04:00:00.000Z')
    expect(highs.y[0]).toBe(10.3)
    // the stamp holds the window that ends there; the hour after it, the next window's
    expect(heldAt(highs, stamps[1]!)).toBe(17.4)
    expect(heldAt(highs, new Date(stamps[1]!.getTime() + HOUR))).toBe(13.9)
    expect(highs.x[highs.x.length - 1]!.toISOString()).toBe('2026-10-16T06:00:00.000Z')
    expect(highs.y.includes(null)).toBe(false)
    // in order of time, no date twice
    const times = highs.x.map(x => x.getTime())
    expect(times).toEqual([...new Set(times)].sort((a, b) => a - b))
  })

  it('cuts the window the chart ends in, and draws none past it', () => {
    const cut = extremeWindowSteps(stamps, maxima, 12 * HOUR, from, Date.parse('2026-10-15T12:00:00Z'), HOUR)
    expect(cut.x[cut.x.length - 1]!.toISOString()).toBe('2026-10-15T12:00:00.000Z')
    expect(cut.y[cut.y.length - 1]).toBe(17.4)
    const early = extremeWindowSteps(stamps, maxima, 12 * HOUR, from, Date.parse('2026-10-15T05:00:00Z'), HOUR)
    expect(early.y.every(y => y === 10.3)).toBe(true)
  })

  it('draws no point for a window the chart shows none of, where it ends or starts at a stamp', () => {
    // the chart ends where the second window starts, and starts where the first ends
    const atEnd = extremeWindowSteps(stamps, maxima, 12 * HOUR, from, stamps[0]!.getTime(), HOUR)
    expect(atEnd.y.every(y => y === 10.3)).toBe(true)
    expect(atEnd.x[atEnd.x.length - 1]).toEqual(stamps[0])
    // the first hour shown is the end of the first window, which that window holds
    const atStart = extremeWindowSteps(stamps, maxima, 12 * HOUR, stamps[0]!.getTime(), to, HOUR)
    expect(atStart.x[0]).toEqual(stamps[0])
    expect(atStart.y[0]).toBe(10.3)
    expect(heldAt(atStart, new Date(stamps[0]!.getTime() + HOUR))).toBe(17.4)
    // and where it is the only window shown, it is shown
    const only = extremeWindowSteps([stamps[0]!], [10.3], 12 * HOUR, stamps[0]!.getTime(), to, HOUR)
    expect([only.x.map(x => x.toISOString()), only.y]).toEqual([['2026-10-15T06:00:00.000Z'], [10.3]])
  })

  it('breaks the line where a stamp has no value, and keeps overlapping windows apart', () => {
    const gap = extremeWindowSteps(stamps, [10.3, Number.NaN, 13.9], 12 * HOUR, from, to, HOUR)
    // no bound for the hours of the window it would have held, and the next window is its own
    expect(heldAt(gap, hours[10]!)).toBeUndefined()
    expect(heldAt(gap, hours[20]!)).toBe(13.9)
    expect(gap.y.filter(y => y === null)).toHaveLength(1)
    // stamps 6 hours apart under a window of 12: each holds the hours since the stamp before it
    const sixHourly = extremeWindowSteps([new Date(start + 2 * HOUR), new Date(start + 8 * HOUR)], [1, 2], 12 * HOUR, from, to, HOUR)
    expect(heldAt(sixHourly, new Date(start + 5 * HOUR))).toBe(2)
    expect(heldAt(sixHourly, new Date(start + 1 * HOUR))).toBe(1)
  })

  it('has a point at each step of the chart, so a hover finds the bound at any hour', () => {
    const highs = extremeWindowSteps(stamps, maxima, 12 * HOUR, from, to, 3 * HOUR)
    const hoursOfDay = highs.x.map(x => x.toISOString().slice(11, 13))
    expect(hoursOfDay).toContain('09')
    expect(hoursOfDay).not.toContain('08')
  })
})

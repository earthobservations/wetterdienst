import { describe, expect, it } from 'vitest'
import { classifyPrecip, findNearestIndex, interpSeries, wetBulbApprox } from '../../app/utils/meteogram'

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

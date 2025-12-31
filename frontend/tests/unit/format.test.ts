import { describe, it, expect } from 'vitest'
import { formatDate } from '../../app/utils/format'

describe('Date formatting utilities', () => {
  it('formats date with microseconds', () => {
    const input = '1934-01-01T00:00:00.000000+00:00'
    const expected = '1934-01-01T00:00:00Z'
    expect(formatDate(input)).toBe(expected)
  })

  it('handles date without microseconds', () => {
    const input = '2024-12-31T12:30:45+00:00'
    const expected = '2024-12-31T12:30:45Z'
    expect(formatDate(input)).toBe(expected)
  })

  it('handles date with negative timezone', () => {
    const input = '2024-01-01T00:00:00.000000-00:00'
    const expected = '2024-01-01T00:00:00Z'
    expect(formatDate(input)).toBe(expected)
  })

  it('preserves date without timezone', () => {
    const input = '2024-01-01T00:00:00'
    expect(formatDate(input)).toBe(input)
  })
})

describe('Number formatting utilities', () => {
  it('formats numbers with fixed decimals', () => {
    expect((123.456789).toFixed(2)).toBe('123.46')
    expect((10).toFixed(2)).toBe('10.00')
  })

  it('formats large numbers with locale', () => {
    expect((1000000).toLocaleString()).toMatch(/1[,.]000[,.]000/)
  })

  it('handles null values', () => {
    const value: number | null = null
    expect(value?.toFixed(2) ?? '-').toBe('-')
  })
})

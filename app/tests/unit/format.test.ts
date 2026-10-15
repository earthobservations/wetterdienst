import { describe, expect, it } from 'vitest'
import { formatDate, formatNumber } from '../../app/utils/format'

describe('date formatting utilities', () => {
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

describe('number formatting utilities', () => {
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

describe('formatNumber', () => {
  // the codes the app's locales have, as `useI18n().locale` gives them (nuxt.config.ts)
  it.each([
    ['en', '1,234.50'],
    ['de', '1.234,50'],
    ['de-hh', '1.234,50'],
    ['nl', '1.234,50'],
    ['da', '1.234,50'],
    ['es', '1234,50'],
    ['it', '1234,50'],
    ['lb', '1.234,50'],
  ])('writes 1234.5 to two places in %s as %s', (locale, expected) => {
    expect(formatNumber(1234.5, locale, 2)).toBe(expected)
  })

  it.each(['fr', 'pl', 'cs'])('groups thousands with a space and puts a comma before the fraction in %s', (locale) => {
    // the space is a no-break one, which differs by language, so only its kind is pinned; five
    // digits, since pl leaves four alone
    expect(formatNumber(12345.5, locale, 2)).toMatch(/^12\s345,50$/)
  })

  it('always writes the places asked for, as toFixed does', () => {
    expect(formatNumber(10, 'de', 2)).toBe('10,00')
    expect(formatNumber(0.5, 'en', 1)).toBe('0.5')
    expect(formatNumber(2, 'en', 0)).toBe('2')
  })

  it('rounds to the places asked for', () => {
    expect(formatNumber(2.345, 'en', 1)).toBe('2.3')
  })
})

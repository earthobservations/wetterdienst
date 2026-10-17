import { DateTime } from 'luxon'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatDate, formatDayMonth, formatNumber, plotlyDateLocale, plotlyHoverFormat, plotlySeparators, weekdayShort, withData } from '../../app/utils/format'

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

describe('plotlySeparators', () => {
  // the codes the app's locales have, as `useI18n().locale` gives them (nuxt.config.ts): the decimal
  // character first, then the group's
  it.each([
    ['en', '.,'],
    ['de', ',.'],
    ['de-hh', ',.'],
    ['nl', ',.'],
    ['da', ',.'],
    ['es', ',.'],
    ['it', ',.'],
    ['lb', ',.'],
  ])('writes %s with the separators %s', (locale, expected) => {
    expect(plotlySeparators(locale)).toBe(expected)
  })

  it.each(['fr', 'pl', 'cs'])('writes a comma and a space to group in %s', (locale) => {
    // the space is a no-break one, which differs by language, so only its kind is pinned
    expect(plotlySeparators(locale)).toMatch(/^,\s$/)
  })

  it('is two characters in every language the app has, as Plotly reads them', () => {
    for (const locale of ['en', 'de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb'])
      expect(plotlySeparators(locale)).toHaveLength(2)
  })

  it('agrees with formatNumber on the decimal', () => {
    for (const locale of ['en', 'de', 'fr', 'pl'])
      expect(formatNumber(1.5, locale, 1)).toContain(plotlySeparators(locale)[0])
  })
})

describe('formatDayMonth', () => {
  const date = DateTime.fromISO('2026-10-05T12:00', { zone: 'Europe/Berlin' })

  // the languages the app's locales write (`language` in nuxt.config.ts): day first in every one,
  // and the order and the sign between day and month the language's own
  it.each([
    ['en-GB', '05/10'],
    ['de-DE', '05.10.'],
    ['fr-FR', '05/10'],
    ['it-IT', '05/10'],
    ['nl-NL', '05-10'],
    ['pl-PL', '05.10'],
    ['cs-CZ', '05. 10.'],
    ['da-DK', '05.10'],
    ['lb-LU', '05.10.'],
  ])('writes the 5th of October in %s as %s', (language, expected) => {
    expect(formatDayMonth(date, language)).toBe(expected)
  })

  it('writes the day with no leading zero in Spanish, as the language does', () => {
    expect(formatDayMonth(date, 'es-ES')).toBe('5/10')
  })

  it('writes the day before the month in British English', () => {
    // the American order, which a bare `en` would give, reads the 5th of October as the 10th of May
    expect(formatDayMonth(date, 'en-GB')).toBe('05/10')
    expect(formatDayMonth(DateTime.fromISO('2026-10-15'), 'en-GB')).toBe('15/10')
  })

  it('names the day of the zone the DateTime stands in', () => {
    // 23:30 UTC on the 5th is the 6th in Berlin
    const late = DateTime.fromISO('2026-10-05T23:30:00Z', { zone: 'Europe/Berlin' })
    expect(formatDayMonth(late, 'de-DE')).toBe('06.10.')
  })
})

describe('a language the browser has no data for', () => {
  // Chrome ships none for Luxembourgish: its Intl then writes the system's language instead, and
  // the 5th of October month first for an English reader
  afterEach(() => {
    vi.restoreAllMocks()
  })

  function withoutLuxembourgish() {
    for (const format of [Intl.NumberFormat, Intl.DateTimeFormat]) {
      const supported = format.supportedLocalesOf
      vi.spyOn(format, 'supportedLocalesOf').mockImplementation((languages, options) =>
        supported((languages as string[]).filter(language => !language.startsWith('lb')), options))
    }
  }

  it('asks for German in its place, with its separators and day', () => {
    expect(withData('lb', Intl.NumberFormat.supportedLocalesOf)).toBe('lb')
    withoutLuxembourgish()
    expect(withData('lb', Intl.NumberFormat.supportedLocalesOf)).toBe('de-LU')
    expect(withData('lb-LU', Intl.DateTimeFormat.supportedLocalesOf)).toBe('de-LU')
    expect(plotlySeparators('lb')).toBe(',.')
    expect(formatNumber(1234.5, 'lb', 2)).toBe('1.234,50')
    expect(formatDayMonth(DateTime.fromISO('2026-10-05'), 'lb-LU')).toBe('05.10.')
  })

  it('leaves a language it has data for as it is', () => {
    withoutLuxembourgish()
    expect(withData('fr-FR', Intl.DateTimeFormat.supportedLocalesOf)).toBe('fr-FR')
    expect(withData('en', Intl.NumberFormat.supportedLocalesOf)).toBe('en')
  })
})

// Thursday the 15th of October 2026, as the languages of the app's locales write it (nuxt.config.ts)
describe('weekdays and the hover heading in the language', () => {
  const thursday = DateTime.fromISO('2026-10-15')
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it.each([
    ['en-GB', 'Thu', '%a %d/%m %H:%M'],
    ['de-DE', 'Do', '%a %d.%m. %H:%M'],
    ['fr-FR', 'jeu.', '%a %d/%m %H:%M'],
    ['es-ES', 'jue', '%a %d/%m %H:%M'],
    ['it-IT', 'gio', '%a %d/%m %H:%M'],
    ['pl-PL', 'czw.', '%a %d.%m %H:%M'],
    ['nl-NL', 'do', '%a %d-%m %H:%M'],
    ['cs-CZ', 'čt', '%a %d. %m. %H:%M'],
    ['da-DK', 'tors.', '%a %d.%m %H:%M'],
    ['lb-LU', 'Don', '%a %d.%m. %H:%M'],
  ])('writes %s as %s with the heading format %s', (language, weekday, hoverformat) => {
    expect(weekdayShort(thursday, language)).toBe(weekday)
    expect(plotlyHoverFormat(language)).toBe(hoverformat)
    const { format } = plotlyDateLocale(language)
    // Sunday first, as Plotly has it
    expect(format.shortDays[4]).toBe(weekday)
    expect(format.shortDays).toHaveLength(7)
    expect(format.days).toHaveLength(7)
    expect(format.months).toHaveLength(12)
    expect(format.shortMonths).toHaveLength(12)
  })

  it('writes Luxembourgish as German where the browser has no data for it', () => {
    vi.spyOn(Intl.DateTimeFormat, 'supportedLocalesOf').mockReturnValue([])
    expect(weekdayShort(thursday, 'lb-LU')).toBe('Do')
    expect(plotlyDateLocale('lb-LU').format.shortDays[4]).toBe('Do')
    expect(plotlyHoverFormat('lb-LU')).toBe('%a %d.%m. %H:%M')
  })

  it('names the days from Sunday and the months from January', () => {
    const { format } = plotlyDateLocale('de-DE')
    expect(format.days[0]).toBe('Sonntag')
    expect(format.days[6]).toBe('Samstag')
    expect(format.months[0]).toBe('Januar')
    expect(format.months[9]).toBe('Oktober')
  })
})

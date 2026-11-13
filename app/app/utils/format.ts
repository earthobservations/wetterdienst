import type { DateTime } from 'luxon'

/**
 * Format date string by removing unnecessary microseconds and simplifying timezone
 * @param dateStr - Date string in ISO format
 * @returns Formatted date string
 * @example
 * formatDate('1934-01-01T00:00:00.000000+00:00') // '1934-01-01T00:00:00Z'
 */
export function formatDate(dateStr: string): string {
  return dateStr.replace(/\.0+([+-])/, '$1').replace(/[+-]00:00$/, 'Z')
}

/**
 * Languages a browser can lack data for, and the one to write them with instead. Chrome ships no
 * Luxembourgish: `Intl` then falls back to the system's language, which for an English reader
 * writes "10/05" for the 5th of October, month first. German writes the same day, month and
 * separators as Luxembourgish does.
 */
const STAND_IN: Record<string, string> = { 'lb': 'de-LU', 'lb-LU': 'de-LU' }

/**
 * The app's own locale codes that no browser knows as a language: Hamburgisch (`de-hh`, Low German) is written
 * with German's data. Chrome resolves the code to German itself; it is mapped before the browser is asked, so that
 * the tag is the one German has and does not depend on how a browser reads an unknown region.
 */
const OWN_CODES: Record<string, string> = { 'de-hh': 'de-DE' }

/**
 * The language to hand `Intl`, for a locale code of the app (`lb`, `de-hh`) or a language tag (`en-GB`): the one
 * asked for where the browser has its data, else its stand-in. Every `Intl` and `toLocale*String` call of the app
 * is given what this answers, never the bare code (`tests/unit/i18n-source.test.ts`).
 */
export function withData(language: string, supported: (languages: string[]) => string[]): string {
  const asked = OWN_CODES[language] ?? language
  return supported([asked]).length ? asked : (STAND_IN[asked] ?? asked)
}

/**
 * Format a number for display in the active UI language: the locale's decimal separator and
 * grouping, and always `digits` fractions, as `toFixed` does -- which writes a point in every
 * language. Not for values that leave the app (exports, API parameters): those stay machine-readable.
 * @example
 * formatNumber(3.14159, 'de', 2) // '3,14'
 */
export function formatNumber(value: number, locale: string, digits: number): string {
  return new Intl.NumberFormat(withData(locale, Intl.NumberFormat.supportedLocalesOf), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
}

/**
 * The decimal and the group character of a language, as Plotly's `layout.separators` takes them:
 * the two characters in one string, the decimal first. Plotly writes the numbers of a hover text
 * (`%{y:.1f}`) and of the axes with them, and with none writes a point in every language. The
 * group character is the one the language writes (a no-break space in French and Polish), though
 * Plotly shows it only for a format that asks for grouping (`,.1f`).
 * @example
 * plotlySeparators('de') // ',.'
 */
export function plotlySeparators(locale: string): string {
  const parts = new Intl.NumberFormat(withData(locale, Intl.NumberFormat.supportedLocalesOf)).formatToParts(1234567.5)
  const decimal = parts.find(part => part.type === 'decimal')?.value ?? '.'
  const group = parts.find(part => part.type === 'group')?.value ?? ','
  return `${decimal}${group}`
}

/**
 * A day and a month as the language writes them, with no year and the zero the language pads with:
 * "05.10." in German, "05/10" in British English (the English the app speaks), "05-10" in Dutch.
 * The language is the region-bearing tag of the locale (`en-GB`, `de-DE`), as a bare `en` would
 * write the American "10/05". The day is the one the DateTime stands in, in its own zone.
 * @example
 * formatDayMonth(DateTime.fromISO('2026-10-05'), 'de-DE') // '05.10.'
 */
export function formatDayMonth(date: DateTime, language: string): string {
  return date.setLocale(withData(language, Intl.DateTimeFormat.supportedLocalesOf)).toLocaleString({ day: '2-digit', month: '2-digit' })
}

/**
 * The short weekday ("Thu", "Do.", "jeu.") as the language writes it, for the DateTime's own day. The
 * language is the region-bearing tag of the locale (`en-GB`), as {@link formatDayMonth} takes it, and
 * not the app's code (`lb`, `de-hh`), which a browser may know nothing of.
 * @example
 * weekdayShort(DateTime.fromISO('2026-10-15'), 'de-DE') // 'Do.'
 */
export function weekdayShort(date: DateTime, language: string): string {
  return date.setLocale(withData(language, Intl.DateTimeFormat.supportedLocalesOf)).toFormat('ccc')
}

/**
 * The names of the weekdays and the months of a language in the shape of a Plotly locale
 * (`config.locales`, with `config.locale` naming it), which the basic bundle lacks: its `%a` and `%b`
 * write English in every language. Sunday comes first, as Plotly has it.
 * @example
 * plotlyDateLocale('de-DE').format.shortDays[4] // 'Do.'
 */
export function plotlyDateLocale(language: string): { format: Record<'days' | 'shortDays' | 'months' | 'shortMonths', string[]> } {
  const tag = withData(language, Intl.DateTimeFormat.supportedLocalesOf)
  const names = (options: Intl.DateTimeFormatOptions, days: number[]) =>
    days.map(day => new Intl.DateTimeFormat(tag, { ...options, timeZone: 'UTC' }).format(Date.UTC(2023, 0, day)))
  const week = [1, 2, 3, 4, 5, 6, 7] // 2023-01-01 is a Sunday
  const months = Array.from({ length: 12 }, (_, month) => Date.UTC(2023, month, 1))
  const month = (style: 'long' | 'short') => months.map(ms => new Intl.DateTimeFormat(tag, { month: style, timeZone: 'UTC' }).format(ms))
  return {
    format: {
      days: names({ weekday: 'long' }, week),
      shortDays: names({ weekday: 'short' }, week),
      months: month('long'),
      shortMonths: month('short'),
    },
  }
}

/**
 * The moment a forecast run was made, as the language writes a date and a time, in UTC with the zone's name:
 * "15.10.2026, 04:00 UTC" in German, "15/10/2026, 04:00 UTC" in British English. The language is the region-bearing
 * tag of the locale (`en-GB`), as {@link formatDayMonth} takes it. A run is hourly at most, so no seconds.
 * @example
 * formatRunTime('2026-10-15T04:00:00+00:00', 'de-DE') // '15.10.2026, 04:00 UTC'
 */
export function formatRunTime(iso: string, language: string): string {
  return new Intl.DateTimeFormat(withData(language, Intl.DateTimeFormat.supportedLocalesOf), {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(new Date(iso))
}

/**
 * The hour of a moment as the language writes a time of day, in the given zone (UTC by default): "04:00" in German
 * and British English, "04.00" in Danish. The language is the region-bearing tag of the locale (`en-GB`), as
 * {@link formatDayMonth} takes it. Never built from its parts (`HH:mm`), which is the German separator in every language.
 * @example
 * formatHour(Date.UTC(2026, 9, 15, 4), 'da-DK') // '04.00'
 */
export function formatHour(ms: number, language: string, timeZone = 'UTC'): string {
  return new Intl.DateTimeFormat(withData(language, Intl.DateTimeFormat.supportedLocalesOf), {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone,
  }).format(ms)
}

/**
 * {@link formatHour} for many moments of one language and zone: the formatter is built once, which is what a
 * chart that writes a label for each of its hours needs.
 */
export function hourFormatter(language: string, timeZone = 'UTC'): (ms: number) => string {
  const format = new Intl.DateTimeFormat(withData(language, Intl.DateTimeFormat.supportedLocalesOf), {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone,
  })
  return ms => format.format(ms)
}

/**
 * The format of the Meteogram's hover heading (Plotly's `hoverformat`, d3's time format): the short
 * weekday, the day and month in the order and with the separators the language writes them, and the
 * time. The weekday's name comes from {@link plotlyDateLocale}.
 * @example
 * plotlyHoverFormat('de-DE') // '%a %d.%m. %H:%M'
 */
export function plotlyHoverFormat(language: string): string {
  const parts = new Intl.DateTimeFormat(withData(language, Intl.DateTimeFormat.supportedLocalesOf), { day: '2-digit', month: '2-digit', timeZone: 'UTC' })
    .formatToParts(Date.UTC(2023, 9, 15))
  const dayMonth = parts.map(part => part.type === 'day' ? '%d' : part.type === 'month' ? '%m' : part.value.replaceAll('%', '%%')).join('')
  return `%a ${dayMonth} %H:%M`
}

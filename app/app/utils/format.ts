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
  return numberFormat(locale, digits).format(value)
}

/**
 * A number with its sign written out for a rise, as an anomaly is (`+0.8`): the minus of a fall is the language's own.
 * A value that rounds to zero is written without a sign, whichever way it rounds from (`0.0`, not `-0.0`).
 * @example
 * formatSigned(0.84, 'en', 1) // '+0.8'
 * formatSigned(-0.004, 'en', 1) // '0.0'
 */
export function formatSigned(value: number, locale: string, digits: number): string {
  return numberFormat(locale, digits, true).format(value)
}

// A table of 240 rows of 13 numbers is 3,000 calls, and a formatter is dear to make (it was 17 ms of the Meteogram's mount):
// one for each language, number of digits and way of writing the sign, and none that outlives the `Intl` that made it (a test swaps it)
const numberFormats = new Map<string, Intl.NumberFormat>()
let numberFormatClass = Intl.NumberFormat
function numberFormat(locale: string, digits: number, signed = false): Intl.NumberFormat {
  if (Intl.NumberFormat !== numberFormatClass) {
    numberFormats.clear()
    numberFormatClass = Intl.NumberFormat
  }
  const key = `${locale}|${digits}|${signed}`
  let format = numberFormats.get(key)
  if (!format) {
    format = new Intl.NumberFormat(withData(locale, Intl.NumberFormat.supportedLocalesOf), { minimumFractionDigits: digits, maximumFractionDigits: digits, ...(signed ? { signDisplay: 'exceptZero' as const } : {}) })
    numberFormats.set(key, format)
  }
  return format
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

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
 * Format a number for display in the active UI language: the locale's decimal separator and
 * grouping, and always `digits` fractions, as `toFixed` does -- which writes a point in every
 * language. Not for values that leave the app (exports, API parameters): those stay machine-readable.
 * @example
 * formatNumber(3.14159, 'de', 2) // '3,14'
 */
export function formatNumber(value: number, locale: string, digits: number): string {
  return new Intl.NumberFormat(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
}

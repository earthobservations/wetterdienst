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

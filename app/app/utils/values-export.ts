import type { Value } from '#shared/types/api'

/**
 * Quote one CSV field where it needs it: a comma, a quote or a line break in it. `taken_station_ids`
 * holds several ids separated by commas, and written bare it spilled into the columns after it.
 */
function csvField(value: unknown): string {
  if (value === null || value === undefined)
    return ''
  const text = String(value)
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

/**
 * Write values as CSV, in the columns given and in that order, a header row first.
 *
 * @param values - The rows, as the table shows them
 * @param columns - The columns the table shows
 * @returns The CSV text, or an empty string for no rows
 * @example
 * valuesToCsv([{ station_id: '01048', value: 1.5 }], ['station_id', 'value'])
 * // 'station_id,value\n01048,1.5'
 */
export function valuesToCsv(values: Value[], columns: (keyof Value)[]): string {
  if (!values.length)
    return ''
  const rows = values.map(row => columns.map(column => csvField(row[column])).join(','))
  return [columns.join(','), ...rows].join('\n')
}

/**
 * Write values as JSON, `{ "values": [...] }` as the REST API answers, each row with the columns given.
 *
 * @param values - The rows, as the table shows them
 * @param columns - The columns the table shows
 * @returns The JSON text
 */
export function valuesToJson(values: Value[], columns: (keyof Value)[]): string {
  const rows = values.map(row => Object.fromEntries(columns.map(column => [column, row[column] ?? null])))
  return JSON.stringify({ values: rows }, null, 2)
}

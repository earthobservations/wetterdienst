/** A row as the data viewer holds it: a value, or a wide-shaped row, or whatever the query panel made. */
type Row = object

// A query panel's COUNT(*) comes from DuckDB as a BigInt, which JSON cannot write: a number where
// that is exact, its digits past 2^53
function bigintValue(value: bigint): number | string {
  const number = Number(value)
  return Number.isSafeInteger(number) ? number : value.toString()
}

function field(row: Row, column: string): unknown {
  return (row as Record<string, unknown>)[column]
}

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
 * The columns to export: every column the rows carry, those the table knows in its order first, then
 * the rest in the order they first appear.
 *
 * All of them, whatever the column picker shows: the picker hides `resolution` and `dataset` by
 * default and follows the mode selected now rather than the one the rows were fetched in, and a
 * file that left out what it hid lost fields the REST API's answer always had. A wide-shaped
 * answer (one column per parameter) and a query panel's own columns (`avg_value`) come after.
 *
 * @param values - The rows, as the table holds them
 * @param order - The columns the table knows, in its order
 * @returns The columns, each once
 */
export function exportColumns(values: Row[], order: string[]): string[] {
  // every row's keys, not the first row's alone: a row set need not give each row every column
  const carried = new Set<string>()
  for (const row of values) {
    for (const column in row)
      carried.add(column)
  }
  return [...order.filter(column => carried.has(column)), ...[...carried].filter(column => !order.includes(column))]
}

/**
 * Write rows as CSV, in the columns given and in that order, a header row first.
 *
 * @param values - The rows
 * @param columns - The columns to write
 * @returns The CSV text, or an empty string for no rows
 * @example
 * valuesToCsv([{ station_id: '01048', value: 1.5 }], ['station_id', 'value'])
 * // 'station_id,value\n01048,1.5'
 */
export function valuesToCsv(values: Row[], columns: string[]): string {
  if (!values.length)
    return ''
  const rows = values.map(row => columns.map(column => csvField(field(row, column))).join(','))
  // a query panel names an unaliased column after its expression, `round(avg("value"), 2)`
  return [columns.map(csvField).join(','), ...rows].join('\n')
}

/**
 * Write rows as JSON, `{ "values": [...] }` as the REST API answers, compact as it answers by default.
 *
 * @param values - The rows
 * @param columns - The columns to write
 * @returns The JSON text
 */
export function valuesToJson(values: Row[], columns: string[]): string {
  const rows = values.map(row => Object.fromEntries(columns.map(column => [column, field(row, column) ?? null])))
  return JSON.stringify({ values: rows }, (_key, value) => typeof value === 'bigint' ? bigintValue(value) : value)
}

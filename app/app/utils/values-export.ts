/** A row as the data viewer holds it: a value, or a wide-shaped row, or whatever the query panel made. */
type Row = object

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
 * The columns to export: those the table shows, in the table's order, then every column the rows
 * carry that the table has no column for, in the order they first appear.
 *
 * The table's columns are a fixed set, which a wide-shaped answer (one column per parameter) or a
 * query panel's own columns (`avg_value`) go past: those are exported although the table cannot
 * show them. A column the table has but hides, because it was taken out of the column picker,
 * stays out, and so does one no row carries, such as `value` in a wide shape.
 *
 * @param values - The rows, as the table holds them
 * @param shown - The columns the table shows, in its order
 * @param known - Every column the table can show
 * @returns The columns, each once
 */
export function exportColumns(values: Row[], shown: string[], known: string[]): string[] {
  const columns = new Set(shown.filter(column => values.some(row => column in row)))
  for (const row of values) {
    for (const column of Object.keys(row)) {
      if (!known.includes(column))
        columns.add(column)
    }
  }
  return [...columns]
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
  return [columns.join(','), ...rows].join('\n')
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
  // a query panel's COUNT(*) comes back from DuckDB as a BigInt, which JSON has no way to write;
  // a count is far below where a number loses precision
  return JSON.stringify({ values: rows }, (_key, value) => typeof value === 'bigint' ? Number(value) : value)
}

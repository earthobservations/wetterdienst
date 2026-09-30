/** A column of a query result, as the Arrow schema DuckDB answers with describes it. */
export interface ArrowField {
  name: string
  type: { toString: () => string, scale?: number }
}

/**
 * Turn one value Arrow's `toJSON()` gave into the plain value the table, the chart and anything else
 * that takes the query panel's rows read, by the type of its column (GH-2068).
 *
 * - A timestamp or date comes as milliseconds since the epoch: it becomes an ISO string, as the
 *   REST API writes a timestamp.
 * - A BIGINT (`COUNT(*)`) comes as a BigInt, which JSON cannot write: it becomes a number.
 * - A DECIMAL comes as an object holding the unscaled integer (12.34 at scale 2 as 1234): it
 *   becomes the number it stands for.
 * - A struct, list or map comes as an object: it becomes its JSON text, as a CSV cell holds text.
 */
export function plainValue(value: unknown, field: ArrowField): unknown {
  if (value === null || value === undefined)
    return null
  const type = field.type.toString()
  if ((type.startsWith('Timestamp') || type.startsWith('Date')) && typeof value === 'number')
    return new Date(value).toISOString()
  if (typeof value === 'bigint')
    return Number(value)
  if (type.startsWith('Decimal'))
    return Number(value) / 10 ** (field.type.scale ?? 0)
  if (typeof value === 'object')
    return JSON.stringify(value, (_key, inner) => typeof inner === 'bigint' ? Number(inner) : inner)
  return value
}

/**
 * Turn the rows of a query result into plain values, column by column, as `plainValue` does.
 *
 * @param rows - The rows, as Arrow's `toJSON()` gives them
 * @param fields - The result's columns, from its schema
 * @returns The rows with plain values
 */
export function plainRows(rows: Record<string, unknown>[], fields: ArrowField[]): Record<string, unknown>[] {
  return rows.map(row => Object.fromEntries(fields.map(field => [field.name, plainValue(row[field.name], field)])))
}

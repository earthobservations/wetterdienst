/** A column of a query result, as the Arrow schema DuckDB answers with describes it. */
export interface ArrowField {
  name: string
  type: { toString: () => string }
}

type Convert = (value: unknown) => unknown

function jsonText(value: unknown): string {
  return JSON.stringify(value, (_key, inner) => typeof inner === 'bigint' ? Number(inner) : inner)
}

/**
 * A value of a column no type asked anything special of, made plain. DuckDB is opened to answer
 * DECIMAL and BIGINT as doubles (QueryPanel's `castDecimalToDouble`, `castBigIntToDouble`), so a
 * BigInt is left only where that cast does not reach, and becomes a number all the same. Bytes (a
 * BLOB, an interval) become the list of them, and a struct, list or map its JSON text, as a CSV cell
 * holds text.
 */
function plainOther(value: unknown): unknown {
  if (value === null || value === undefined)
    return null
  if (typeof value === 'bigint')
    return Number(value)
  if (ArrayBuffer.isView(value))
    return jsonText(Array.from(value as unknown as ArrayLike<unknown>))
  if (typeof value === 'object')
    return jsonText(value)
  return value
}

/**
 * A timestamp or date, which Arrow gives as milliseconds since the epoch -- fractional for a
 * microsecond timestamp -- written as an ISO timestamp in UTC to the millisecond. Floored, so a
 * moment before 1970 is not rounded towards it. One past what a Date holds (DuckDB's `infinity`) is
 * null, as there is no time to write.
 */
function timestampValue(value: unknown): unknown {
  if (typeof value !== 'number')
    return plainOther(value)
  const date = new Date(Math.floor(value))
  return Number.isFinite(date.getTime()) ? date.toISOString().replace(/Z$/, '+00:00') : null
}

function converterFor(field: ArrowField): Convert {
  const type = field.type.toString()
  return type.startsWith('Timestamp') || type.startsWith('Date') ? timestampValue : plainOther
}

/**
 * Turn the rows of a query result into the plain values the table, the chart and anything else that
 * takes the query panel's rows read, by the type of each column, read once (GH-2068). The rows,
 * fresh from Arrow's `toJSON()`, are changed in place.
 *
 * A name given to two columns holds the last one's value, as `toJSON()` keeps, so it takes the last
 * one's converter.
 *
 * @param rows - The rows, as Arrow's `toJSON()` gives them
 * @param fields - The result's columns, from its schema
 * @returns The same rows, with plain values
 */
export function plainRows(rows: Record<string, unknown>[], fields: ArrowField[]): Record<string, unknown>[] {
  const converters = new Map<string, Convert>()
  for (const field of fields)
    converters.set(field.name, converterFor(field))
  for (const row of rows) {
    for (const [name, convert] of converters)
      row[name] = convert(row[name])
  }
  return rows
}
